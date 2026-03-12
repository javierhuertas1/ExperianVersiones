import json
import boto3
import logging
import os
import sys
from urllib.parse import unquote_plus

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ssm_client = boto3.client('ssm')
glue_client = boto3.client('glue')

# Define base path for parameter store

ASCEND_OPS_BASE_BUCKET = os.environ.get('ASCEND_OPS_BASE_BUCKET')
ASCEND_OPS_BASE_PARAMETER_STORE = os.environ.get('ASCEND_OPS_BASE_PARAMETER_STORE')

def handler(event, context):
    """
    AWS Lambda function handler to process S3 events and trigger Glue jobs.
    
    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The context object provided by AWS Lambda.
    
    Returns:
        dict: A response indicating the result of the processing.
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    logger.info(f"Lambda function context: {context}")
    
    processed_records = 0
    failed_records = 0
    
    try:
        # Process each record in the event
        for record in event.get('Records', []):
            try:                # Extract S3 bucket and key information
                bucket_name = record['s3']['bucket']['name']
                object_key = unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Processing object: s3://{bucket_name}/{object_key}")
                  # Get config parameters first to validate S3 key structure
                config_params = _get_config_parameters(ASCEND_OPS_BASE_PARAMETER_STORE)
                if config_params is None:
                    logger.error("Failed to retrieve config parameters")
                    failed_records += 1
                    continue
                
                # Validate that the entry parameter exists for S3 key validation
                entry_param_key = f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/entry"
                if entry_param_key not in config_params:
                    logger.error(f"Missing required config parameter: {entry_param_key}")
                    failed_records += 1
                    continue
                
                # Parse and validate the object key using configurable entry path
                if not _validate_and_extract_key_parts(object_key, config_params):
                    failed_records += 1
                    continue
                
                product_name, type_document, filename = _extract_key_components(object_key, config_params)
                logger.info(f"Extracted - Product: {product_name}, Type: {type_document}, File: {filename}")
                
                # Extract document number from filename for validation
                document_number = filename.split('_')[0] if '_' in filename else filename.split('.')[0]
                logger.info(f"Extracted document number: {document_number}")
                
                # Get product-specific parameters
                product_params = _get_product_parameters(ASCEND_OPS_BASE_PARAMETER_STORE, product_name)
                if product_params is None:
                    logger.error(f"Failed to retrieve product parameters for {product_name}")
                    failed_records += 1
                    continue
                
                # Validate document type against parameter store
                if not _validate_document_type(product_name, type_document, product_params):
                    logger.error(f"Document type validation failed for {product_name}/{type_document}")
                    failed_records += 1
                    continue
                  # Retrieve and validate job parameters
                job_params = _get_required_job_parameters(product_name, config_params, product_params)
                if job_params is None:
                    failed_records += 1
                    continue
                
                input_value, output_value, product_code, base_processed, folder_route, external_bucket_name = job_params
                
                # Start Glue job
                if _start_glue_job(bucket_name, object_key, product_name, type_document, document_number, input_value, output_value, product_code, base_processed, folder_route, external_bucket_name):
                    processed_records += 1
                    logger.info(f"Successfully processed: {object_key}")
                else:
                    failed_records += 1
                    
            except Exception as e:
                logger.error(f"Error processing record: {e}")
                failed_records += 1
                continue
        
        # Return response based on processing results
        if failed_records > 0:
            logger.warning(f"Processing completed with {failed_records} failures out of {processed_records + failed_records} records")
            return {
                "statusCode": 207,  # Multi-Status
                "body": json.dumps({
                    "message": f"Partial success: {processed_records} processed, {failed_records} failed",
                    "processed": processed_records,
                    "failed": failed_records
                })
            }
        else:
            logger.info(f"All {processed_records} records processed successfully")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": f"Successfully processed {processed_records} S3 event(s) and triggered Glue job(s)",
                    "processed": processed_records
                })
            }
        
    except Exception as e:
        logger.error(f"Critical error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def _validate_and_extract_key_parts(object_key, config_params):
    """
    Validate the S3 object key format using configurable paths.
    
    Args:
        object_key (str): The S3 object key to validate
        config_params (dict): Configuration parameters containing path settings
        
    Returns:
        bool: True if valid format, False otherwise    """
    key_parts = object_key.split('/')
    
    # Get configurable entry path from config parameters
    # Parameter key should be like "/ascend-ops/config/entry" with value "ascend-ops/entradas"
    entry_param_key = f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/entry"
    entry_path_full = config_params.get(entry_param_key, 'ascend-ops/entradas')  # Default fallback
    
    # Debug logging to understand the parameter value
    logger.info(f"Entry parameter key: {entry_param_key}")
    logger.info(f"Entry path from config: '{entry_path_full}'")
    
    # Clean up entry_path_full (remove leading/trailing slashes) before splitting
    clean_entry_path = entry_path_full.strip('/')
    expected_key_start = clean_entry_path.split('/')  # Should be ['ascend-ops', 'entradas']
    logger.info(f"Expected key start parts: {expected_key_start}")
    
    if len(key_parts) < len(expected_key_start) + 3:  # Need at least path + product + type + filename
        logger.error(f"Invalid key format - insufficient parts. Expected: {clean_entry_path}/<product_name>/<type_document>/<filename>, got: {object_key}")
        return False
    
    # Validate the key starts with the expected path
    key_prefix = key_parts[:len(expected_key_start)]
    if key_prefix != expected_key_start:
        logger.error(f"Invalid key format - expected '{'/'.join(expected_key_start)}' prefix, got: '{'/'.join(key_prefix)}'")
        return False
    
    # Extract components after the base path
    remaining_parts = key_parts[len(expected_key_start):]
    if len(remaining_parts) < 3:
        logger.error(f"Invalid key format - need product_name, type_document, and filename after {clean_entry_path}")
        return False
        
    product_name, type_document, filename = remaining_parts[0], remaining_parts[1], remaining_parts[2]
    
    if not product_name or not type_document or not filename:
        logger.error(f"Invalid key format - empty product_name, type_document, or filename in: {object_key}")
        return False
        
    if not filename.endswith('.csv'):
        logger.warning(f"File is not a CSV: {filename}. Processing anyway...")
        
    return True


def _extract_key_components(object_key, config_params):
    """
    Extract product_name, type_document, and filename from object key.
    
    Args:
        object_key (str): The S3 object key
        config_params (dict): Configuration parameters containing path settings
        
    Returns:
        tuple: (product_name, type_document, filename)
    """
    key_parts = object_key.split('/')
    # Get configurable entry path to determine offset
    entry_param_key = f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/entry"
    entry_path_full = config_params.get(entry_param_key, 'ascend-ops/entradas')
    # Clean up entry_path_full (remove leading/trailing slashes) before splitting
    clean_entry_path = entry_path_full.strip('/')
    expected_key_start = clean_entry_path.split('/')
    base_path_length = len(expected_key_start)
    
    # Extract components after the base path
    product_name = key_parts[base_path_length]
    type_document = key_parts[base_path_length + 1] 
    filename = key_parts[base_path_length + 2]
    
    return product_name, type_document, filename


def _get_parameters_by_path_recursive(path, with_decryption=False):
    """
    Retrieve all parameters under a specified path using get_parameters_by_path.
    
    Args:
        path (str): The parameter path to retrieve
        with_decryption (bool): Whether to decrypt SecureString parameters
        
    Returns:
        dict: Dictionary mapping parameter names to their values, or None if error
    """
    try:
        parameters = {}
        next_token = None
        
        while True:
            kwargs = {
                'Path': path,
                'Recursive': True,
                'WithDecryption': with_decryption
            }
            
            if next_token:
                kwargs['NextToken'] = next_token
            
            response = ssm_client.get_parameters_by_path(**kwargs)
            
            # Process parameters from this batch
            for param in response.get('Parameters', []):
                parameters[param['Name']] = param['Value']
            
            # Check if there are more parameters to fetch
            next_token = response.get('NextToken')
            if not next_token:
                break
        
        logger.info(f"Retrieved {len(parameters)} parameters from path: {path}")
        return parameters
        
    except Exception as e:
        logger.error(f"Error retrieving parameters from path {path}: {e}")
        return None


def _get_config_parameters(ascend_ops_base):
    """
    Retrieve all configuration parameters from /ascend-ops/config/.
    
    Args:
        ascend_ops_base (str): The base path for ascend-ops parameters
        
    Returns:
        dict: Dictionary mapping parameter names to their values, or None if error
    """
    config_path = f"{ascend_ops_base}/config"
    
    return _get_parameters_by_path_recursive(config_path)


def _get_product_parameters(ascend_ops_base, product_name):
    """
    Retrieve all product-specific parameters for a given product.
    
    Args:
        ascend_ops_base (str): The base path for ascend-ops parameters
        product_name (str): The product name
        
    Returns:
        dict: Dictionary mapping parameter names to their values, or None if error
    """
    product_path = f"{ascend_ops_base}/{product_name}"
    
    return _get_parameters_by_path_recursive(product_path)


def _get_required_job_parameters(product_name, config_params, product_params):
    """
    Retrieve and validate all required parameters for Glue job execution.
    
    Args:
        product_name (str): The product name
        config_params (dict): Pre-fetched config parameters
        product_params (dict): Pre-fetched product parameters
          Returns:
        tuple: (input_value, output_value, product_code, base_processed, folder_route, external_bucket_name) or None if error
    """
    try:
        # Define required parameter keys
        required_config_keys = [
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/da-input",
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/da-output",
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/processed",
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/output",
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/external-bucket-name"
        ]
        
        required_product_keys = [
            f"{ASCEND_OPS_BASE_PARAMETER_STORE}/{product_name}/codigo"
        ]
        
        # Check for missing config parameters
        missing_config = [key for key in required_config_keys if key not in config_params]
        if missing_config:
            logger.error(f"Missing config parameters: {missing_config}")
            return None
        
        # Check for missing product parameters
        missing_product = [key for key in required_product_keys if key not in product_params]
        if missing_product:
            logger.error(f"Missing product parameters: {missing_product}")
            return None
          # Extract values
        input_value = config_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/da-input"]
        output_value = config_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/da-output"]
        base_processed = config_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/processed"]
        folder_route = config_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/output"]
        external_bucket_name = config_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/config/external-bucket-name"]
        product_code = product_params[f"{ASCEND_OPS_BASE_PARAMETER_STORE}/{product_name}/codigo"]
        
        # Log retrieved parameters
        logger.info(f"Retrieved config parameters: da-input={input_value}, da-output={output_value}, processed={base_processed}, output={folder_route}, external-bucket={external_bucket_name}")
        logger.info(f"Retrieved product code for {product_name}: {product_code}")
          # Validate parameter values are not empty
        validations = [
            (input_value, "Input parameter"),
            (output_value, "Output parameter"),
            (product_code, "Product code parameter"),
            (base_processed, "Base processed parameter"),
            (folder_route, "Folder route parameter"),
            (external_bucket_name, "External bucket parameter")
        ]
        
        for value, param_name in validations:
            if not value.strip():
                logger.error(f"{param_name} is empty")
                return None
            
        return input_value, output_value, product_code, base_processed, folder_route, external_bucket_name
        
    except Exception as e:
        logger.error(f"Error processing job parameters: {e}")
        return None


def _start_glue_job(bucket_name, object_key, product_name, type_document, document_number, input_value, output_value, product_code, base_processed, folder_route, external_bucket_name):
    """
    Start the Glue job with the provided parameters.
    
    Args:
        bucket_name (str): S3 bucket name
        object_key (str): S3 object key
        product_name (str): Product name        
        type_document (str): Document type
        document_number (str): Document number extracted from filename
        input_value (str): Input parameter value (path like "in/peru")
        output_value (str): Output parameter value (path like "output/peru")
        product_code (str): Product code from parameter store
        base_processed (str): Base processed path from parameter store
        folder_route (str): Folder route for correlative checking
        external_bucket_name (str): External bucket name from parameter store
        
    Returns:
        bool: True if job started successfully, False otherwise
    """
    glue_job_name = os.environ.get('GLUE_JOB_NAME')
    
    if not glue_job_name:
        logger.error("GLUE_JOB_NAME environment variable not set")
        return False
    
    # input_value and output_value contain just the paths (e.g., "in/peru", "output/peru")
    # external_bucket_name contains the full bucket name from SSM parameter
    logger.info(f"Input path: {input_value}")
    logger.info(f"Output path: {output_value}")
    logger.info(f"External bucket: {external_bucket_name}")
    
    # Clean up base_processed and folder_route to remove trailing slashes
    clean_base_processed = base_processed.rstrip('/')
    clean_folder_route = folder_route.rstrip('/')
      # Prepare job arguments - pass paths and external bucket separately
    job_arguments = {
        '--source_bucket': bucket_name,
        '--source_key': object_key,
        '--product_name': product_name,
        '--type_document': type_document,
        '--document_number': document_number,
        '--input_value': input_value,
        '--output_value': output_value,
        '--product_code': product_code,
        '--base_processed': clean_base_processed,
        '--folder_route': clean_folder_route,
        '--external_bucket_name': external_bucket_name
    }
    
    try:
        # Sanitize job arguments for logging - but keep original values for actual job execution
        safe_job_args = {k: str(v) for k, v in job_arguments.items()}
        logger.info(f"Starting Glue job: {glue_job_name} with arguments: {safe_job_args}")
        
        response = glue_client.start_job_run(
            JobName=glue_job_name,
            Arguments=job_arguments
        )
        
        job_run_id = response['JobRunId']
        logger.info(f"Successfully started Glue job: {glue_job_name} with JobRunId: {job_run_id}")
        return True
        
    except glue_client.exceptions.InvalidInputException as e:
        logger.error(f"Invalid input for Glue job: {e}")
        return False
    except glue_client.exceptions.EntityNotFoundException as e:
        logger.error(f"Glue job not found: {glue_job_name}. Error: {e}")
        return False
    except Exception as e:
        logger.error(f"Error starting Glue job: {e}")
        return False


def _validate_document_type(product_name, type_document, product_params):
    """
    Validate if the type_document matches the expected value in parameter store.
    
    Args:
        product_name (str): The product name (e.g., "business_score")
        type_document (str): The document type from S3 path
        product_params (dict): Pre-fetched product parameters
        
    Returns:
        bool: True if valid, False otherwise
    """
    try:
        # Check both possible parameter keys based on actual parameter structure
        base_path = f"{ASCEND_OPS_BASE_PARAMETER_STORE}/{product_name}"
        
        pj_param_key = f"{base_path}/pj-document"
        pn_param_key = f"{base_path}/pn-document"
        
        # Collect valid (non-empty) parameters
        valid_params = []
        
        for param_key in [pj_param_key, pn_param_key]:
            if param_key in product_params:
                expected_type = product_params[param_key]
                param_type = 'pj-document' if 'pj-document' in param_key else 'pn-document'
                
                logger.info(f"Found {param_type} parameter: {param_key} = {expected_type}")
                
                # Check if parameter is not empty
                if expected_type and expected_type.strip():
                    valid_params.append((param_key, expected_type, param_type))
                    
                    # Check if type_document matches this parameter
                    if type_document == expected_type:
                        logger.info(f"Document type {type_document} matches {param_type} parameter")
                        return True
                else:
                    logger.warning(f"{param_type} parameter exists but is empty: {param_key}")
        
        # Check if at least one valid parameter exists
        if not valid_params:
            logger.error(f"No valid (non-empty) document type parameters found for {product_name}. At least one of pj-document or pn-document must exist and be non-empty.")
            return False
        
        # If we reach here, at least one parameter exists but none matched
        valid_types = [param[1] for param in valid_params]
        logger.error(f"Document type {type_document} does not match any expected parameter values for {product_name}. Valid types: {valid_types}")
        return False
        
    except Exception as e:
        logger.error(f"Error validating document type: {e}")
        return False


