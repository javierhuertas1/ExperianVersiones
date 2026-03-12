# =============================================================================
# Outputs for IAM Roles and Bucket Information
# =============================================================================

# Source bucket outputs
output "source_bucket_name" {
  description = "Name of the source bucket"
  value       = module.source_bucket.s3_bucket_id
}

output "source_bucket_arn" {
  description = "ARN of the source bucket"
  value       = module.source_bucket.s3_bucket_arn
}

output "source_bucket_salidas_path" {
  description = "S3 path to the salidas folder for external team access"
  value       = "s3://${module.source_bucket.s3_bucket_id}/${var.bucket_prefix}/salidas/"
}

# External bucket outputs (conditional)
output "external_bucket_name" {
  description = "Name of the external bucket"
  value       = var.external_bucket_name != "" ? var.external_bucket_name : "Not configured"
}

output "external_bucket_arn" {
  description = "ARN of the external bucket"
  value       = var.external_bucket_name != "" ? local.external_bucket_arn : "Not configured"
}

# IAM Role outputs (conditional)
output "job_script_execution_role_arn" {
  description = "ARN of the job script execution role"
  value       = var.external_bucket_name != "" ? module.job_script_execution_role[0].role_arn : "Not created - external bucket not configured"
}

output "job_script_execution_role_name" {
  description = "Name of the job script execution role"
  value       = var.external_bucket_name != "" ? module.job_script_execution_role[0].role_name : "Not created - external bucket not configured"
}

output "s3_replication_role_arn" {
  description = "ARN of the S3 replication role"
  value       = var.external_bucket_name != "" ? module.s3_replication_role[0].role_arn : "Not created - external bucket not configured"
}

output "s3_replication_role_name" {
  description = "Name of the S3 replication role"
  value       = var.external_bucket_name != "" ? module.s3_replication_role[0].role_name : "Not created - external bucket not configured"
}

output "effective_replication_role_arn" {
  description = "ARN of the role actually used for S3 replication (external if provided, otherwise internal)"
  value = var.external_bucket_name != "" ? (
    var.external_role_to_replication != "" ? 
    var.external_role_to_replication : 
    module.s3_replication_role[0].role_arn
  ) : "Not configured"
}

# Cross-account information
output "is_cross_account_setup" {
  description = "Whether this is a cross-account setup"
  value       = local.is_cross_account
}

output "external_account_id" {
  description = "External bucket account ID"
  value       = var.external_bucket_name != "" ? local.external_account_id : "Not configured"
}

# Lambda function outputs
output "lambda_function_name" {
  description = "Name of the job launcher Lambda function"
  value       = module.job-launcher.function_name
}

output "lambda_function_arn" {
  description = "ARN of the job launcher Lambda function"
  value       = module.job-launcher.lambda_function_arn
}

# Glue outputs
output "glue_database_name" {
  description = "Name of the Glue catalog database"
  value       = module.glue_data_processing.database_id
}

output "glue_database_arn" {
  description = "ARN of the Glue catalog database"
  value       = module.glue_data_processing.database_arn
}

output "glue_job_names" {
  description = "List of Glue job names"
  value       = module.glue_data_processing.job_ids
}

output "glue_job_arns" {
  description = "List of Glue job ARNs"
  value       = module.glue_data_processing.job_arns
}

output "glue_service_role_arn" {
  description = "ARN of the Glue service role"
  value       = module.glue_data_processing.role_arn
}

output "glue_cloudwatch_log_group" {
  description = "CloudWatch log group for Glue jobs"
  value       = module.glue_data_processing.cloudwatch_log_group
}

# Glue scripts bucket outputs
output "glue_scripts_bucket_name" {
  description = "Name of the Glue scripts bucket"
  value       = module.glue_scripts_bucket.s3_bucket_id
}

output "glue_scripts_bucket_arn" {
  description = "ARN of the Glue scripts bucket"
  value       = module.glue_scripts_bucket.s3_bucket_arn
}