import json
import boto3
import logging
import os
import re
import sys
from urllib.parse import unquote_plus
from typing import Dict, Optional, Tuple

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')

# Environment variables
ASCEND_OPS_BASE = os.environ.get('ASCEND_OPS_BASE', '/ascend-ops')
BUCKET_NAME = os.environ.get('BUCKET_NAME')

def handler(event, context):
    """
    AWS Lambda function handler to process replicated output files from output/peru/ 
    and move them to the structured ascend-ops/salidas/<business_type>/<document_type>/<document_number>/ location.
    
    This lambda moves files from the replication output folder to the organized salidas structure
    based on business rules and SSM parameter configuration.
    
    Args:
        event (dict): The S3 event data passed to the Lambda function.
        context (LambdaContext): The context object provided by AWS Lambda.
    
    Returns:
        dict: A response indicating the result of the processing.
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        # Process each record in the event
        for record in event.get('Records', []):
            if record.get('eventSource') == 'aws:s3':
                process_s3_event(record)
                
        return {
            'statusCode': 200,
            'body': json.dumps('Output files moved to salidas successfully')
        }
        
    except Exception as e:
        logger.error(f"Error processing event: {e}")
        raise


def process_s3_event(record):
    """Process a single S3 event record for output to salidas movement"""
    try:
        # Extract bucket and key from the event
        bucket_name = record['s3']['bucket']['name']
        object_key = unquote_plus(record['s3']['object']['key'])
        
        logger.info(f"Processing output file: s3://{bucket_name}/{object_key}")
        
        # Parse the file path to extract components
        file_info = parse_file_path(object_key)
        if not file_info:
            logger.warning(f"Could not parse output file path: {object_key}")
            return
        
        # Since we only trigger on .log files, look for both .log and .out files
        paired_files = get_paired_files(bucket_name, file_info)
        
        # Get parameter store mapping (to get the destination base path)
        param_mapping = get_parameter_mapping()
        
        # Track the source folder for cleanup
        source_folder = '/'.join(object_key.split('/')[:-1])  # e.g., output/peru/20129876543/business_score or output/peru/20321456789
        
        # Process all paired files
        files_moved = []
        for file_key in paired_files:
            # Re-parse each file to get proper info
            current_file_info = parse_file_path(file_key)
            if not current_file_info:
                continue
                
            # Determine the target path in salidas structure
            target_path = determine_target_path(current_file_info, param_mapping)
            if not target_path:
                logger.warning(f"Could not determine salidas target path for: {file_key}")
                continue
                
            # Move the file from output to salidas
            move_file(bucket_name, file_key, target_path)
            files_moved.append(file_key)
        
        # Clean up empty source folders if we moved all files from them
        if files_moved:
            cleanup_source_folders(bucket_name, source_folder)
        
    except Exception as e:
        logger.error(f"Error processing S3 event: {e}")
        raise


def get_paired_files(bucket_name: str, file_info: Dict) -> list:
    """
    Get both .log and .out files if they exist for the same document
    Since we only trigger on .log files, we always check for the corresponding .out file
    
    Returns:
        list: List of file keys to process
    """
    try:
        # Extract the base path and filename without extension
        original_key = file_info['original_key']
        base_path = '/'.join(original_key.split('/')[:-1])  # output/peru/20321456789
        base_filename = file_info['filename'].rsplit('.', 1)[0]  # filename without extension
        
        # Build both file keys
        log_key = f"{base_path}/{base_filename}.log"
        out_key = f"{base_path}/{base_filename}.out"
        
        files_to_process = []
        
        # Always add the .log file (since that's what triggered us)
        files_to_process.append(log_key)
        logger.info(f"Processing .log file: {log_key}")
        
        # Check if corresponding .out file exists
        try:
            s3_client.head_object(Bucket=bucket_name, Key=out_key)
            files_to_process.append(out_key)
            logger.info(f"Found corresponding .out file: {out_key}")
        except s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                logger.info(f"No corresponding .out file found: {out_key}")
            else:
                logger.warning(f"Error checking .out file {out_key}: {str(e)}")
        
        logger.info(f"Files to process: {files_to_process}")
        return files_to_process
            
    except Exception as e:
        logger.error(f"Error getting paired files: {str(e)}")
        # Fallback to processing just the original file
        return [file_info['original_key']]


def parse_file_path(object_key: str) -> Optional[Dict]:
    """
    Parse the file path to extract document number, correlative, product code, etc.
    
    Expected formats: 
    - output/peru/<document_number>/<document_number>val<correlative>-<product_code>-YYMM.<extension>
    - output/peru/<document_number>/<business_type>/<document_number>val<correlative>-<product_code>-YYMM.<extension>
    
    Examples: 
    - output/peru/20321456789/20321456789val000001-370-2506.log
    - output/peru/20129876543/business_score/20129876543val000001-370-2507.log
    
    Returns:
        dict: Parsed file information or None if parsing fails
    """
    # Pattern to match the expected file structure with optional business_type folder
    pattern = r'^output/peru/(\d+)(?:/([^/]+))?/(\d+)val(\d+)-(\d+)-(\d{4})\.(log|out)$'
    
    match = re.match(pattern, object_key)
    if not match:
        logger.error(f"File path does not match expected pattern: {object_key}")
        return None
        
    document_number = match.group(1)
    business_type = match.group(2)  # Optional - could be None or a string like 'business_score'
    document_number_check = match.group(3)
    correlative = match.group(4)
    product_code = match.group(5)
    year_month = match.group(6)
    extension = match.group(7)
    
    # Verify that document numbers match
    if document_number != document_number_check:
        logger.error(f"Document numbers don't match in filename: {document_number} vs {document_number_check}")
        return None
    
    # Determine document type based on business rules
    document_type = determine_document_type(document_number)
    
    return {
        'original_key': object_key,
        'document_number': document_number,
        'business_type': business_type,  # New field for business type folder
        'correlative': correlative,
        'product_code': product_code,
        'year_month': year_month,
        'extension': extension,
        'document_type': document_type,
        'filename': object_key.split('/')[-1]
    }


def determine_document_type(document_number: str) -> str:
    """
    Determine document type based on business rules:
    1. If document_number starts with 10 or 20, and has length 11, will be pj
    2. If document_number is shorter, will be pn
    3. If is longer than 11, it's an error
    
    Returns:
        str: 'pj', 'pn', or 'error'
    """
    length = len(document_number)
    
    if length > 11:
        return 'error'
    elif length == 11 and (document_number.startswith('10') or document_number.startswith('20')):
        return 'pj'
    else:
        return 'pn'


def get_parameter_mapping() -> Dict:
    """
    Retrieve all parameter store values starting with /ascend-ops/ 
    to build product mapping
    
    Returns:
        dict: Mapping of product codes to product names and document types
    """
    try:
        response = ssm_client.get_parameters_by_path(
            Path=ASCEND_OPS_BASE,
            Recursive=True
        )
        
        parameters = {}
        for param in response.get('Parameters', []):
            parameters[param['Name']] = param['Value']
            
        # Process paginated results if any
        while 'NextToken' in response:
            response = ssm_client.get_parameters_by_path(
                Path=ASCEND_OPS_BASE,
                Recursive=True,
                NextToken=response['NextToken']
            )
            for param in response.get('Parameters', []):
                parameters[param['Name']] = param['Value']
        
        logger.info(f"Retrieved {len(parameters)} parameters from {ASCEND_OPS_BASE}")
        
        # Build product mapping
        product_mapping = {}
        
        for param_name, param_value in parameters.items():
            # Parse parameter names like /ascend-ops/business_score/codigo
            parts = param_name.split('/')
            if len(parts) >= 4:  # ['', 'ascend-ops', 'product_name', 'config_type']
                product_name = parts[3]
                config_type = parts[4]
                
                if product_name not in product_mapping:
                    product_mapping[product_name] = {}
                    
                product_mapping[product_name][config_type] = param_value
        
        logger.info(f"Built product mapping for {len(product_mapping)} products")
        return product_mapping
        
    except Exception as e:
        logger.error(f"Error retrieving parameter mapping: {str(e)}")
        raise


def determine_target_path(file_info: Dict, param_mapping: Dict) -> Optional[str]:
    """
    Determine the target path in salidas structure based on product mapping
    Structure: ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>
    
    Returns:
        str: Target path like 'ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>'
    """
    product_code = file_info['product_code']
    document_type = file_info['document_type']
    document_number = file_info['document_number']
    filename = file_info['filename']
    
    # Get the output base path from parameter store
    output_base = param_mapping.get('config', {}).get('output', 'ascend-ops/salidas/')
    # Ensure output_base ends with / for proper path construction
    if not output_base.endswith('/'):
        output_base += '/'
    
    # Handle error case (document number too long)
    if document_type == 'error':
        error_filename = f"e{filename}"
        # For error cases, use first available product as fallback
        if param_mapping:
            # Find first product that's not 'config'
            first_product = next((k for k in param_mapping.keys() if k != 'config'), 'unknown')
            return f"{output_base}{first_product}/error/{document_number}/{error_filename}"
        else:
            return f"{output_base}unknown/error/{document_number}/{error_filename}"
    
    # Find the product that matches this product code (excluding 'config')
    matching_product = None
    for product_name, product_config in param_mapping.items():
        if product_name != 'config' and product_config.get('codigo') == product_code:
            matching_product = product_name
            break
    
    if not matching_product:
        logger.warning(f"No product found for product code: {product_code}")
        return None
    
    # Get the document type configuration
    document_type_key = f"{document_type}-document"
    document_type_value = param_mapping[matching_product].get(document_type_key)
    
    if not document_type_value:
        logger.warning(f"No document type configuration found for {matching_product}/{document_type_key}")
        return None
    
    # Build the full hierarchical path: ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>
    target_path = f"{output_base}{matching_product}/{document_type_value}/{document_number}/{filename}"
    logger.info(f"Target salidas path determined: {target_path}")
    
    return target_path


def move_file(bucket_name: str, source_key: str, target_key: str):
    """
    Move file from output location to salidas location within the same bucket
    """
    try:
        # Copy the object to the new location
        copy_source = {
            'Bucket': bucket_name,
            'Key': source_key
        }
        
        logger.info(f"Moving from output to salidas: {source_key} -> {target_key}")
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=bucket_name,
            Key=target_key
        )
        
        # Delete the original object
        logger.info(f"Deleting original output file: {source_key}")
        s3_client.delete_object(
            Bucket=bucket_name,
            Key=source_key
        )
        
        logger.info(f"Successfully moved file from output to salidas: {source_key} -> {target_key}")
        
    except Exception as e:
        logger.error(f"Error moving file from output to salidas {source_key} -> {target_key}: {str(e)}")
        raise


def cleanup_source_folders(bucket_name: str, folder_path: str):
    """
    Clean up empty folders in the source path hierarchy, starting from the deepest level.
    For paths like 'output/peru/20129876543/business_score', this will:
    1. First try to clean up 'output/peru/20129876543/business_score/'
    2. Then try to clean up 'output/peru/20129876543/' if it becomes empty
    
    Args:
        bucket_name (str): The S3 bucket name
        folder_path (str): The deepest folder path to start cleanup from
    """
    try:
        # Split the path into parts
        path_parts = folder_path.split('/')
        
        # Start from the deepest folder and work our way up
        for i in range(len(path_parts), 2, -1):  # Stop at 'output/peru' level
            current_folder = '/'.join(path_parts[:i])
            
            # Skip if we're at the 'output' or 'output/peru' level (too broad to clean up)
            if current_folder in ['output', 'output/peru']:
                continue
                
            if cleanup_empty_folder(bucket_name, current_folder):
                logger.info(f"Successfully cleaned up folder: {current_folder}")
            else:
                # If this folder is not empty, don't check parent folders
                logger.info(f"Folder not empty, stopping cleanup: {current_folder}")
                break
                
    except Exception as e:
        logger.warning(f"Error during hierarchical folder cleanup: {str(e)}")


def cleanup_empty_folder(bucket_name: str, folder_path: str) -> bool:
    """
    Check if the source output folder is empty and delete it if so
    
    Args:
        bucket_name (str): The S3 bucket name
        folder_path (str): The folder path to check (e.g., 'output/peru/20321456789')
        
    Returns:
        bool: True if folder was empty and cleaned up, False if folder was not empty or cleanup failed
    """
    try:
        # Ensure folder path ends with / for proper S3 prefix search
        if not folder_path.endswith('/'):
            folder_path += '/'
        
        logger.info(f"Checking if output folder is empty: {folder_path}")
        
        # List objects in the folder
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=folder_path,
            MaxKeys=1  # We only need to know if there's at least one object
        )
        
        # If no objects found in the folder, it's empty
        if 'Contents' not in response or len(response['Contents']) == 0:
            logger.info(f"Output folder is empty, deleting: {folder_path}")
            
            # Delete the folder "object" (S3 folders are just empty objects ending with /)
            try:
                s3_client.delete_object(
                    Bucket=bucket_name,
                    Key=folder_path
                )
                logger.info(f"Successfully deleted empty output folder: {folder_path}")
                return True  # Successfully cleaned up
            except s3_client.exceptions.ClientError as e:
                if e.response['Error']['Code'] == 'NoSuchKey':
                    logger.info(f"Output folder object doesn't exist (that's okay): {folder_path}")
                    return True  # Consider this successful (folder didn't exist anyway)
                else:
                    logger.warning(f"Error deleting output folder {folder_path}: {str(e)}")
                    return False  # Cleanup failed
        else:
            logger.info(f"Output folder is not empty, keeping: {folder_path}")
            return False  # Folder not empty
            
    except Exception as e:
        logger.warning(f"Error checking/cleaning up output folder {folder_path}: {str(e)}")
        return False  # Cleanup failed
