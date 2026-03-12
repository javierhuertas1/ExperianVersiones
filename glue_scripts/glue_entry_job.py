import sys
import boto3
import botocore
import re
from datetime import datetime
from awsglue.utils import getResolvedOptions

# ------------------------------------------------------------
# Security and utility functions
# ------------------------------------------------------------

def sanitize_for_logging(input_string):
    """
    Sanitize input string for safe logging by removing CRLF characters.
    
    Args:
        input_string (str): Input string to sanitize
        
    Returns:
        str: Sanitized string safe for logging
    """
    if not input_string:
        return ""
    
    # Remove carriage return and line feed characters
    sanitized = input_string.replace('\r', '').replace('\n', '')
    
    # Replace other control characters with spaces
    sanitized = re.sub(r'[\x00-\x1F\x7F]', ' ', sanitized)
    
    return sanitized

def sanitize_for_path(input_string):
    """
    Sanitize input string for safe use in S3 key paths.
    Removes directory traversal characters and other dangerous sequences.
    
    Args:
        input_string (str): Input string to sanitize
        
    Returns:
        str: Sanitized string safe for S3 key use
    """
    if not input_string:
        return ""
    
    # Remove directory traversal sequences
    sanitized = re.sub(r'\.\./', '', input_string)
    sanitized = re.sub(r'\.\.\\', '', sanitized)
    
    # Remove other dangerous characters
    sanitized = re.sub(r'[<>:"|?*]', '', sanitized)
    
    # Remove leading/trailing whitespace and dots
    sanitized = sanitized.strip(' .')
    
    # Ensure it doesn't start with / or \
    sanitized = sanitized.lstrip('/\\')
    
    return sanitized

def safe_print(message):
    """
    Safely print messages with sanitized content.
    
    Args:
        message (str): Message to print
    """
    safe_message = sanitize_for_logging(message)
    print(safe_message)

# ------------------------------------------------------------
# Expected job parameters
# ------------------------------------------------------------
args = getResolvedOptions(
    sys.argv,
    ['JOB_NAME', 'source_bucket', 'source_key', 'product_name', 'type_document', 
     'document_number', 'input_value', 'output_value', 'product_code', 
     'base_processed', 'folder_route', 'external_bucket_name']
)

source_bucket = args['source_bucket']
source_key = args['source_key']
product_name = args['product_name']
type_document = args['type_document']
document_number = args['document_number']
input_value = args['input_value']
output_value = args['output_value']
product_code = args['product_code']
base_processed = args['base_processed']
folder_route = args['folder_route']
external_bucket_name = args.get('external_bucket_name', '')


def get_next_correlative(s3_client, source_bucket, folder_route, product_name, type_document, document_number, product_code):
    """
    Get the next correlative number by checking existing files in the folder.
    
    Args:
        s3_client: boto3 S3 client
        source_bucket (str): Source bucket name
        folder_route (str): Folder route from parameter store
        product_name (str): Product name
        type_document (str): Document type
        document_number (str): Document number
        product_code (str): Product code
        
    Returns:
        str: Next correlative number as 6-digit string
    """
    current_date = datetime.now()
    current_year = current_date.strftime('%y')  # YY format
    current_month = current_date.strftime('%m')  # MM format
    
    # Build the prefix to search for existing files
    search_prefix = f"{folder_route}/{product_name}/{type_document}/{document_number}/"
    
    try:
        # List objects with the prefix
        response = s3_client.list_objects_v2(
            Bucket=source_bucket,
            Prefix=search_prefix
        )
        
        # Pattern to match files: <document_number>val<correlative>-<product_code>-YYMM.(log|out)
        pattern = rf"{re.escape(document_number)}val(\d{{6}})-{re.escape(product_code)}-{current_year}{current_month}\.(log|out)$"
        
        max_correlative = 0
        
        if 'Contents' in response:
            for obj in response['Contents']:
                filename = obj['Key'].split('/')[-1]
                match = re.match(pattern, filename)
                if match:
                    correlative = int(match.group(1))
                    max_correlative = max(max_correlative, correlative)
        
        # Return next correlative as 6-digit string
        next_correlative = max_correlative + 1
        return f"{next_correlative:06d}"
        
    except Exception as e:
        safe_print(f"Error getting correlative number: {e}")
        safe_print(f"Starting with correlative 000001")
        return "000001"

def generate_new_filename(document_number, correlative, product_code):
    """
    Generate the new filename according to the specified format.
    
    Args:
        document_number (str): Document number from original filename
        correlative (str): 6-digit correlative number
        product_code (str): Product code from parameter store
        
    Returns:
        str: New filename in format <document_number>val<correlative>-<product_code>-YYMM.csv
    """
    current_date = datetime.now()
    year_month = current_date.strftime('%y%m')  # YYMM format
    
    return f"{document_number}val{correlative}-{product_code}-{year_month}.csv"

# ------------------------------------------------------------
# Initialize boto3 S3 client
# ------------------------------------------------------------
s3 = boto3.client('s3')

safe_print(f"Processing file from: s3://{source_bucket}/{sanitize_for_logging(source_key)}")
safe_print(f"Document number: {sanitize_for_logging(document_number)}")
safe_print(f"Product name: {sanitize_for_logging(product_name)}")
safe_print(f"Document type: {sanitize_for_logging(type_document)}")
safe_print(f"Product code: {sanitize_for_logging(product_code)}")
safe_print(f"Base processed: {sanitize_for_logging(base_processed)}")
safe_print(f"Folder route: {sanitize_for_logging(folder_route)}")

# ------------------------------------------------------------
# 1) Generate new filename with correlative
# ------------------------------------------------------------
safe_print("Generating new filename with correlative...")

# Get next correlative number
correlative = get_next_correlative(s3, source_bucket, folder_route, product_name, type_document, document_number, product_code)
safe_print(f"Next correlative: {sanitize_for_logging(correlative)}")

# Generate new filename
new_filename = generate_new_filename(document_number, correlative, product_code)
safe_print(f"New filename: {sanitize_for_logging(new_filename)}")

# ------------------------------------------------------------
# 2) Copy to processed phase
# ------------------------------------------------------------
safe_print("Copying to processed phase...")

# Build processed key using base_processed parameter - sanitize path components
safe_product_name = sanitize_for_path(product_name)
safe_type_document = sanitize_for_path(type_document)
processed_key = f"{base_processed}/{safe_product_name}/{safe_type_document}/{new_filename}"

copy_source = {
    'Bucket': source_bucket,
    'Key': source_key
}

try:
    # Copy to processed folder with new filename
    s3.copy_object(
        Bucket=source_bucket,
        CopySource=copy_source,
        Key=processed_key
    )
    safe_print(f"✔ Successfully copied to processed: s3://{source_bucket}/{sanitize_for_logging(processed_key)}")
except botocore.exceptions.ClientError as e:
    safe_print(f"✘ Failed to copy to processed: {e}")
    raise

# ------------------------------------------------------------
# 3) Copy to destination bucket
# ------------------------------------------------------------
safe_print("Copying to destination bucket...")

# Use external bucket for destination, input_value contains the path prefix
dest_bucket_name = external_bucket_name if external_bucket_name else source_bucket
dest_prefix = input_value  # This should be something like "in/peru"

# Build destination key with sanitized path components
safe_document_number = sanitize_for_path(document_number)
safe_product_name = sanitize_for_path(product_name)
dest_key = f"{dest_prefix}/{safe_document_number}/{safe_product_name}/{new_filename}"

try:
    # Copy to destination bucket with new filename
    s3.copy_object(
        Bucket=dest_bucket_name,
        CopySource=copy_source,
        Key=dest_key
    )
    safe_print(f"✔ Successfully copied to destination: s3://{dest_bucket_name}/{sanitize_for_logging(dest_key)}")
except botocore.exceptions.ClientError as e:
    safe_print(f"✘ Failed to copy to destination: {e}")
    raise

# ------------------------------------------------------------
# 4) Delete the original from "entradas"
# ------------------------------------------------------------
safe_print(f"Deleting original from entradas: s3://{source_bucket}/{sanitize_for_logging(source_key)}")
try:
    s3.delete_object(
        Bucket=source_bucket,
        Key=source_key
    )
    safe_print("✔ Deletion of original succeeded.")
except botocore.exceptions.ClientError as e:
    safe_print(f"✘ Failed to delete original: {e}")
    raise

safe_print("Glue job completed successfully.")
