import json
import boto3
import logging
import os
import re
import sys
from urllib.parse import unquote_plus
from datetime import datetime

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
ssm_client = boto3.client('ssm')
sqs_client = boto3.client('sqs')

# Define base path for parameter store
ASCEND_OPS_BASE_PARAMETER_STORE = os.environ.get('ASCEND_OPS_BASE_PARAMETER_STORE')

def handler(event, context):
    """
    AWS Lambda function handler to process S3 events for .log files and send to SQS FIFO queue.
    
    Args:
        event (dict): The event data passed to the Lambda function.
        context (LambdaContext): The context object provided by AWS Lambda.
    
    Returns:
        dict: A response indicating the result of the processing.
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    processed_records = 0
    failed_records = 0
    
    try:
        sqs_queue_url = os.environ.get('SQS_QUEUE_URL')
        if not sqs_queue_url:
            logger.error("SQS_QUEUE_URL environment variable not set")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "SQS_QUEUE_URL not configured"})
            }
        
        # Process each record in the event
        for record in event.get('Records', []):
            try:
                # Extract S3 bucket and key information
                bucket_name = record['s3']['bucket']['name']
                object_key = unquote_plus(record['s3']['object']['key'])
                
                logger.info(f"Processing object: s3://{bucket_name}/{object_key}")
                
                # Validate that this is a .log file
                if not object_key.endswith('.log'):
                    logger.info(f"Skipping non-log file: {object_key}")
                    continue
                
                # Validate the S3 key structure for salidas/business_score/RUC path
                if not _validate_invoice_key_structure(object_key):
                    logger.error(f"Invalid key structure for invoice processing: {object_key}")
                    failed_records += 1
                    continue
                  # Extract components from the key
                business_type, filename = _extract_invoice_key_components(object_key)
                if not business_type or not filename:
                    logger.error(f"Failed to extract components from key: {object_key}")
                    failed_records += 1
                    continue
                
                # Parse filename to extract document details
                document_details = _parse_filename(filename)
                if not document_details:
                    logger.error(f"Failed to parse filename: {filename}")
                    failed_records += 1
                    continue
                
                # Get product name from SSM parameter using business_type
                product_display_name = _get_product_name(business_type)
                if not product_display_name:
                    logger.error(f"Failed to get product name for: {business_type}")
                    failed_records += 1
                    continue
                  # Prepare message for SQS
                message_body = {
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                    "business_type": business_type,
                    "product_display_name": product_display_name,
                    "filename": filename,
                    "document_number": document_details["document_number"],
                    "correlative": document_details["correlative"],
                    "product_code": document_details["product_code"],
                    "year_month": document_details["year_month"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Send message to SQS FIFO queue
                if _send_to_sqs_fifo(sqs_queue_url, message_body, business_type, filename):
                    processed_records += 1
                    logger.info(f"Successfully queued for processing: {object_key}")
                else:
                    failed_records += 1
                    
            except Exception as e:
                logger.error(f"Error processing record: {str(e)}")
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
                    "message": f"Successfully processed {processed_records} S3 event(s) and queued for invoice processing",
                    "processed": processed_records
                })
            }
        
    except Exception as e:
        logger.error(f"Critical error processing event: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def _validate_invoice_key_structure(object_key):
    """
    Validate that the S3 object key follows the expected structure:
    /ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>.log
    
    Args:
        object_key (str): The S3 object key to validate
        
    Returns:
        bool: True if valid format, False otherwise
    """
    # Pattern for: ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>.log
    # Document number is typically 8-11 digits
    pattern = r'^ascend-ops/salidas/[^/]+/[^/]+/\d{8,11}/[^/]+\.log$'
    
    if re.match(pattern, object_key):
        return True
    
    logger.error(f"Key does not match expected pattern. Expected: ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>.log, got: {object_key}")
    return False


def _extract_invoice_key_components(object_key):
    """
    Extract business_type and filename from the object key.
    Expected format: ascend-ops/salidas/<business_type>/<document_type>/<document_number>/<filename>.log
    Example: ascend-ops/salidas/business_score/RUC/20321456789/20321456789val000001-370-2506.log
    
    Args:
        object_key (str): The S3 object key
        
    Returns:
        tuple: (business_type, filename) or (None, None) if parsing fails
    """
    try:
        key_parts = object_key.split('/')
        
        # Expected format: ['ascend-ops', 'salidas', '<business_type>', '<document_type>', '<document_number>', '<filename>.log']
        if len(key_parts) >= 6 and key_parts[4].isdigit():
            business_type = key_parts[2]   # Index 2 is business_type (business_score)
            document_type = key_parts[3]   # Index 3 is document_type (RUC)
            document_number = key_parts[4] # Index 4 is document_number (20321456789)
            filename = key_parts[5]        # Index 5 is filename (20321456789val000001-370-2506.log)
            
            logger.info(f"Extracted - business_type: {business_type}, document_type: {document_type}, document_number: {document_number}, filename: {filename}")
            return business_type, filename
        
        else:
            logger.error(f"Invalid key format or insufficient parts: {str(key_parts)}")
            return None, None
            
    except Exception as e:
        logger.error(f"Error extracting components from key {object_key}: {str(e)}")
        return None, None


def _parse_filename(filename):
    """
    Parse the filename to extract document details.
    Expected format: <document_number>val<correlative>-<product_code>-YYMM.log
    Example: 20113604248val000003-370-2506.log
    
    Args:
        filename (str): The filename to parse
        
    Returns:
        dict: Dictionary with parsed components or None if parsing fails
    """
    try:
        # Remove .log extension
        base_name = filename.replace('.log', '')
        
        # Pattern: document_number + 'val' + correlative + '-' + product_code + '-' + YYMM
        pattern = r'^(\d+)val(\d+)-(\d+)-(\d{4})$'
        match = re.match(pattern, base_name)
        
        if not match:
            logger.error(f"Filename does not match expected pattern: {filename}")
            return None
        
        document_number = match.group(1)
        correlative = match.group(2)
        product_code = match.group(3)
        year_month = match.group(4)
        
        return {
            "document_number": document_number,
            "correlative": correlative,
            "product_code": product_code,
            "year_month": year_month
        }
        
    except Exception as e:
        logger.error(f"Error parsing filename {filename}: {str(e)}")
        return None


def _get_product_name(product_key):
    """
    Get the product display name from SSM parameter store.
    Parameter path: /ascend-ops/<product_key>/producto
    
    Args:
        product_key (str): The product key (e.g., business_score)
        
    Returns:
        str: Product display name or None if not found
    """
    try:
        parameter_name = f"{ASCEND_OPS_BASE_PARAMETER_STORE}/{product_key}/producto"
        
        response = ssm_client.get_parameter(
            Name=parameter_name,
            WithDecryption=False
        )
        
        product_name = response['Parameter']['Value']
        logger.info(f"Retrieved product name: {product_name} for key: {product_key}")
        return product_name
        
    except ssm_client.exceptions.ParameterNotFound:
        logger.error(f"Parameter not found: {parameter_name}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving product name from SSM: {str(e)}")
        return None


def _send_to_sqs_fifo(queue_url, message_body, business_type, filename):
    """
    Send message to SQS FIFO queue.
    
    Args:
        queue_url (str): The SQS queue URL
        message_body (dict): The message body to send
        business_type (str): Business type for grouping
        filename (str): Filename for deduplication
        
    Returns:
        bool: True if message sent successfully, False otherwise
    """
    try:
        # Generate message group ID based on business type to ensure ordering per product
        message_group_id = f"invoice-{business_type}"
        
        # Generate deduplication ID based on filename and timestamp to avoid duplicates
        deduplication_id = f"{filename}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(message_body),
            MessageGroupId=message_group_id,
            MessageDeduplicationId=deduplication_id
        )
        
        logger.info(f"Message sent to SQS with MessageId: {response['MessageId']}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending message to SQS: {str(e)}")
        return False
