import json
import boto3
import logging
import csv
import io
import os
from datetime import datetime
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
ASCEND_OPS_BASE_BUCKET = os.environ.get('ASCEND_OPS_BASE_BUCKET')


def build_secure_csv_key(report_month, report_year, product_name, document_type):
    """
    Build S3 key from validated atomic components to prevent directory traversal.
    Following the proposed atomic input validation pattern.
    """
    # 1) Validate atomic inputs
    if not (1 <= report_month <= 12):
        raise ValueError("Invalid month")
    if not (2000 <= report_year <= datetime.now().year):
        raise ValueError("Invalid year")
    if document_type not in ['RUC', 'DNI']:
        raise ValueError("Invalid document type")
    
    # 2) Build filename safely
    date_str = f"{report_month:02d}{str(report_year)[-2:]}"  # e.g. "0625" for June 2025
    filename = f"Facturacion_{product_name}_{date_str}.csv"
    
    # 3) Return the complete key with fixed prefix
    return f"{ASCEND_OPS_BASE_BUCKET}/facturacion/{product_name}/{document_type}/{filename}"


def handler(event, context):
    """
    AWS Lambda function handler to process SQS messages for invoice generation.
    
    Args:
        event (dict): The event data from SQS containing invoice processing messages
        context (LambdaContext): The context object provided by AWS Lambda
    
    Returns:
        dict: A response indicating the result of the processing
    """
    logger.info(f"Received SQS event: {json.dumps(event, default=str)}")
    
    processed_records = 0
    failed_records = 0
    
    try:
        # Process each SQS record
        for record in event.get('Records', []):
            try:
                # Parse the message body
                message_body = json.loads(record['body'])
                logger.info(f"Processing message: {message_body}")
                  # Extract required information
                bucket_name = message_body['bucket_name']
                object_key = message_body['object_key']
                product_display_name = message_body['product_display_name']
                filename = message_body['filename']
                document_number = message_body['document_number']
                year_month = message_body['year_month']
                
                # Process the log file
                if _process_invoice_log(bucket_name, object_key, product_display_name, 
                                      filename, document_number, year_month):
                    processed_records += 1
                    logger.info(f"Successfully processed invoice for: {filename}")
                else:
                    failed_records += 1
                    
            except Exception as e:
                logger.error(f"Error processing SQS record: {e}")
                failed_records += 1
                continue
        
        # Return response
        return {
            "statusCode": 200 if failed_records == 0 else 207,
            "body": json.dumps({
                "message": f"Invoice processing completed: {processed_records} processed, {failed_records} failed",
                "processed": processed_records,
                "failed": failed_records
            })
        }
        
    except Exception as e:
        logger.error(f"Critical error processing SQS event: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }


def _process_invoice_log(bucket_name, object_key, product_display_name, 
                        filename, document_number, year_month):
    """
    Main orchestrator for invoice log processing.
    Single responsibility: coordinate the invoice processing workflow.
    """
    try:
        # Step 1: Read and validate input data
        log_data = _read_log_file_from_s3(bucket_name, object_key)
        if not log_data:
            return False
        
        metrics = _extract_metrics_from_log(log_data)
        if not metrics:
            return False
        
        # Step 2: Get processing parameters
        document_type = _extract_document_type_from_path(object_key)
        month_int, year_int = _parse_year_month(year_month)
        
        # Step 3: Build secure CSV key
        csv_s3_key = build_secure_csv_key(month_int, year_int, product_display_name, document_type)
        logger.info(f"Target CSV file: s3://{bucket_name}/{csv_s3_key}")
        
        # Step 4: Process CSV file
        return _process_csv_file(bucket_name, csv_s3_key, filename, metrics, document_number)
        
    except Exception as e:
        logger.error(f"Error in _process_invoice_log: {e}")
        return False


def _parse_year_month(year_month):
    """
    Parse YYMM format into atomic month and year integers.
    Single responsibility: validate and convert year_month format.
    """
    if not year_month or len(year_month) != 4:
        raise ValueError(f"Invalid year_month format: {year_month}")
    
    month_int = int(year_month[2:4])  # MM as integer (1-12)
    year_int = int("20" + year_month[0:2])  # YYYY as integer (assuming 20XX years)
    
    return month_int, year_int


def _process_csv_file(bucket_name, csv_s3_key, filename, metrics, document_number):
    """
    Handle CSV file processing workflow.
    Single responsibility: manage CSV file operations.
    """
    try:
        # Extract atomic components from the secure key for _read_existing_csv
        # Parse the secure key: ascend-ops/facturacion/{product_name}/{document_type}/Facturacion_{product_name}_{date_str}.csv
        key_parts = csv_s3_key.split('/')
        product_name = key_parts[2]  # Extract product from path
        document_type = key_parts[3]  # Extract document type from path
        
        # Extract month/year from filename: Facturacion_{product_name}_{MMYY}.csv
        filename_part = key_parts[-1]  # Get the filename
        date_part = filename_part.split('_')[-1].replace('.csv', '')  # Get MMYY part
        month_int = int(date_part[:2])  # First 2 digits = month
        year_int = int("20" + date_part[2:])  # Last 2 digits = year (20XX)
        
        # Read existing data using atomic inputs
        existing_rows = _read_existing_csv(bucket_name, month_int, year_int, product_name, document_type)
        
        # Prepare new data
        header_row = _create_csv_header(metrics)
        data_row = _create_csv_data_row(filename, metrics, document_number, header_row)
        
        # Update file
        if _write_csv_file(bucket_name, csv_s3_key, existing_rows, header_row, data_row):
            logger.info(f"Successfully updated CSV file: {csv_s3_key}")
            return True
        else:
            logger.error(f"Failed to update CSV file: {csv_s3_key}")
            return False
            
    except Exception as e:
        logger.error(f"Error processing CSV file: {e}")
        return False


def _extract_document_type_from_path(object_key):
    """
    Extract document type (RUC or DNI) from S3 object key path.
    
    Expected path format: ascend-ops/salidas/{product}/{document_type}/{document_number}/...
    
    Args:
        object_key (str): S3 object key path
        
    Returns:
        str: Document type ('RUC' or 'DNI')
        
    Raises:
        Exception: If document type cannot be extracted or is invalid
    """
    try:
        # Split the path and look for RUC or DNI
        path_parts = object_key.split('/')
        
        # Find RUC or DNI in the path
        for part in path_parts:
            part = part.strip().upper()
            if part in ['RUC', 'DNI']:
                # Simple validation - just check it's a known type
                logger.info(f"Extracted document type '{part}' from object key: {object_key}")
                return part
        
        # If no RUC or DNI found, log the path and raise error
        logger.error(f"Could not find RUC or DNI in object key path: {object_key}")
        raise Exception(f"Document type (RUC/DNI) not found in object key path")
        
    except Exception as e:
        logger.error(f"Error extracting document type from path: {e}")
        raise Exception(f"Failed to parse document type from object key: {str(e)}")


def _read_log_file_from_s3(bucket_name, object_key):
    """
    Read the log file content from S3.
    
    Args:
        bucket_name (str): S3 bucket name
        object_key (str): S3 object key
        
    Returns:
        str: Log file content or None if error
    """
    try:
        # Simple path validation to prevent directory traversal attacks
        if '..' in object_key:
            logger.error(f"Invalid log file S3 key detected: {object_key}")
            return None
            
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        content = response['Body'].read().decode('utf-8')
        logger.info(f"Successfully read log file: {object_key}")
        return content
        
    except ClientError as e:
        logger.error(f"Error reading log file from S3: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error reading log file: {e}")
        return None


def _extract_metrics_from_log(log_content):
    """
    Extract metrics from the log file content.
    
    Args:
        log_content (str): Content of the log file
        
    Returns:
        dict: Dictionary containing extracted metrics or None if error
    """
    try:
        metrics = {}
        lines = log_content.strip().split('\n')
        
        # Parse each line in format: key;value
        for line in lines:
            if ';' in line:
                key, value = line.split(';', 1)
                metrics[key.strip()] = value.strip()
        
        logger.info(f"Extracted metrics: {metrics}")
        
        # Validate required fields exist (basic fields only)
        required_fields = [
            'nombre_archivo', 'fecha_consulta', 'ruc_cliente', 'no_registros_archivo',
            'no_registros_procesados'
        ]
        
        for field in required_fields:
            if field not in metrics:
                logger.error(f"Missing required field in log: {field}")
                return None
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error extracting metrics from log: {e}")
        return None


def _read_existing_csv(bucket_name, report_month, report_year, product_name, document_type):
    """
    Read existing CSV file from S3 using atomic inputs to prevent directory traversal.
    No user input reaches csv.reader - path is built internally from validated components.
    """
    # Build secure S3 key from atomic validated inputs
    csv_s3_key = build_secure_csv_key(report_month, report_year, product_name, document_type)
    
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=csv_s3_key)
        content = response['Body'].read().decode('utf-8')
        rows = list(csv.reader(io.StringIO(content)))
        logger.info("Processing existing CSV file")
        return rows
        
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            logger.info("CSV file does not exist, will create new")
            return []
        else:
            logger.error(f"Error reading CSV file: {e}")
            return []
    except Exception as e:
        logger.error(f"Unexpected error reading CSV: {e}")
        return []


def _create_csv_header(metrics):
    """
    Create CSV header from metrics.
    Single responsibility: build header structure.
    """
    # Basic required columns that should come first
    basic_columns = [
        'Nombre_archivo',
        'Fecha_consulta', 
        'ruc_cliente',
        'NroRegistros_archivos',
        'NroRegistros_procesados'
    ]
    
    # Find additional fields dynamically
    excluded_keys = {'item_reportado'}
    basic_mapping = {
        'fecha_consulta': 'Fecha_consulta',
        'ruc_cliente': 'ruc_cliente', 
        'no_registros_archivo': 'NroRegistros_archivos',
        'no_registros_procesados': 'NroRegistros_procesados'
    }
    
    additional_fields = []
    for key in sorted(metrics.keys()):
        if key not in basic_mapping and key not in excluded_keys:
            additional_fields.append(key)
    
    return basic_columns + additional_fields


def _create_csv_data_row(filename, metrics, document_number, header_row):
    """
    Create CSV data row from metrics.
    Single responsibility: map data to header structure.
    """
    data_row = []
    
    for column in header_row:
        if column == 'Nombre_archivo':
            data_row.append(filename)
        elif column == 'Fecha_consulta':
            data_row.append(metrics.get('fecha_consulta', ''))
        elif column == 'ruc_cliente':
            data_row.append(metrics.get('ruc_cliente', document_number))
        elif column == 'NroRegistros_archivos':
            data_row.append(metrics.get('no_registros_archivo', ''))
        elif column == 'NroRegistros_procesados':
            data_row.append(metrics.get('no_registros_procesados', ''))
        else:
            # Additional dynamic fields
            data_row.append(metrics.get(column, ''))
    
    return data_row


def _write_csv_file(bucket_name, csv_s3_key, existing_rows, header_row, data_row):
    """
    Write CSV file to S3.
    Single responsibility: handle S3 upload.
    """
    try:
        csv_data = _build_csv_data(existing_rows, header_row, data_row)
        csv_content = _convert_to_csv_string(csv_data)
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=csv_s3_key,
            Body=csv_content.encode('utf-8'),
            ContentType='text/csv'
        )
        
        logger.info(f"Successfully uploaded CSV file: {csv_s3_key} with {len(csv_data)} rows")
        return True
        
    except Exception as e:
        logger.error(f"Error writing CSV file: {e}")
        return False


def _build_csv_data(existing_rows, header_row, data_row):
    """
    Build complete CSV data structure.
    Single responsibility: organize CSV data.
    """
    if not existing_rows:
        # New file
        logger.info("Creating new CSV file")
        return [header_row, data_row]
    
    # Existing file - merge data
    logger.info("Adding to existing CSV file")
    existing_header = existing_rows[0] if existing_rows else []
    existing_data_rows = existing_rows[1:] if len(existing_rows) > 1 else []
    
    # Merge headers
    merged_header = _merge_headers(existing_header, header_row)
    csv_data = [merged_header]
    
    # Add new row as second row
    aligned_new_row = _align_row_to_header(data_row, header_row, merged_header)
    csv_data.append(aligned_new_row)
    
    # Add existing data rows
    for existing_row in existing_data_rows:
        aligned_existing_row = _align_row_to_header(existing_row, existing_header, merged_header)
        csv_data.append(aligned_existing_row)
    
    return csv_data


def _convert_to_csv_string(csv_data):
    """
    Convert data structure to CSV string.
    Single responsibility: CSV format conversion.
    """
    output = io.StringIO()
    csv_writer = csv.writer(output)
    csv_writer.writerows(csv_data)
    return output.getvalue()


def _update_csv_file(bucket_name, csv_s3_key, existing_rows, header_row, data_row):
    """
    Legacy wrapper for backward compatibility.
    Single responsibility: delegate to new focused functions.
    """
    return _write_csv_file(bucket_name, csv_s3_key, existing_rows, header_row, data_row)


def _merge_headers(existing_header, new_header):
    """
    Merge existing and new headers to include all unique columns.
    Maintains order: basic columns first, then all other columns sorted alphabetically.
    
    Args:
        existing_header (list): Existing header columns
        new_header (list): New header columns
        
    Returns:
        list: Merged header with all unique columns
    """
    # Basic columns that should always come first
    basic_columns = [
        'Nombre_archivo',
        'Fecha_consulta', 
        'ruc_cliente',
        'NroRegistros_archivos',
        'NroRegistros_procesados'
    ]
    
    # Collect all unique columns
    all_columns = set(existing_header + new_header)
    
    # Separate basic columns from all other columns
    other_columns = [col for col in all_columns if col not in basic_columns]
    
    # Create final header: basic columns first, then all other columns sorted
    final_header = []
    for col in basic_columns:
        if col in all_columns:
            final_header.append(col)
    
    # Add all other columns sorted alphabetically
    final_header.extend(sorted(other_columns))
    
    return final_header


def _align_row_to_header(data_row, original_header, target_header):
    """
    Align a data row from one header format to another header format.
    
    Args:
        data_row (list): Data row to align
        original_header (list): Original header that data_row corresponds to
        target_header (list): Target header format
        
    Returns:
        list: Aligned data row
    """
    if len(data_row) != len(original_header):
        logger.warning(f"Data row length ({len(data_row)}) doesn't match original header length ({len(original_header)})")
        # Pad with empty strings if needed
        while len(data_row) < len(original_header):
            data_row.append('')
    
    # Create mapping from original header to data
    data_map = {}
    for i, header_col in enumerate(original_header):
        if i < len(data_row):
            data_map[header_col] = data_row[i]
        else:
            data_map[header_col] = ''
    
    # Create aligned row based on target header
    aligned_row = []
    for target_col in target_header:
        aligned_row.append(data_map.get(target_col, ''))  # Default to empty string if column not found
    
    return aligned_row
