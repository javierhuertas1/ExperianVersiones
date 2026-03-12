# =============================================================================
# Parameter Store Entries for External Bucket Configuration
# Using EITS Cloud Enablement AWS SSM Parameter Store Wrapper Module
# =============================================================================

# External bucket name parameter
module "external_bucket_name" {
  count  = var.external_bucket_name != "" ? 1 : 0
  source = "./modules/ssm_wrapper"
  
  name        = "/${var.bucket_prefix}/${var.stage}/config/external-bucket-name"
  value       = var.external_bucket_name
  description = "Name of the external bucket for job script operations"
}

# External bucket account ID parameter
module "external_bucket_account_id" {
  count  = var.external_bucket_name != "" ? 1 : 0
  source = "./modules/ssm_wrapper"
  
  name        = "/${var.bucket_prefix}/${var.stage}/config/external-account-id"
  value       = local.external_account_id
  description = "AWS Account ID that owns the external bucket"
}

# S3 replication role ARN parameter (for external teams to configure replication)
module "s3_replication_role_arn" {
  count  = var.external_bucket_name != "" ? 1 : 0
  source = "./modules/ssm_wrapper"
  
  name        = "/${var.bucket_prefix}/${var.stage}/config/s3-replication-role-arn"
  value       = module.s3_replication_role[0].role_arn
  description = "ARN of the IAM role for S3 replication service - used by external teams"
}

# External replication role ARN parameter (when external role is provided)
# This stores the external role ARN for reference by other systems
module "external_replication_role_arn" {
  count  = var.external_bucket_name != "" && var.external_role_to_replication != "" ? 1 : 0
  source = "./modules/ssm_wrapper"
  
  name        = "/${var.bucket_prefix}/${var.stage}/config/external-replication-role-arn"
  value       = var.external_role_to_replication
  description = "ARN of the external IAM role for S3 replication service - provided by external team"
}

module "config_parameters" {
  for_each = local.config_map
  source   = "./modules/ssm_wrapper"
  name        = "/${var.bucket_prefix}/${var.stage}/config/${each.key}"
  value       = "${var.bucket_prefix}/${each.value}/"
  description = "Folder suffix for ${each.key}"
}

module "external_folder_input" {
  source   = "./modules/ssm_wrapper"
  name     = "/${var.bucket_prefix}/${var.stage}/config/da-input"
  value    = "in/peru"
  description = "External folder for input files"
}

module "external_folder_output" {
  source   = "./modules/ssm_wrapper"
  name     = "/${var.bucket_prefix}/${var.stage}/config/da-output"
  value    = "output/peru"
  description = "External folder for input files"
}