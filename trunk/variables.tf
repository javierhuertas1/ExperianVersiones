variable "aws_region" {
  description = "The AWS region to deploy the resources in"
  type        = string
  default     = "us-east-1"
}

variable "stage" {
  description = "The stage of the deployment (e.g., dev, qa, pro)"
  type        = string
  validation {
    condition     = contains(["dev", "qa", "tst", "stg", "pro"], var.stage)
    error_message = "The stage must be dev, qa, tst,stg or pro"
  }
}

variable "app_id" {
  description = "App Id of application."
  type        = string
  default     = "123"
}

variable "cost_string" {
  description = "Cost Center Account."
  type        = string
  default     = "123456"
}

variable "assume_role_arn" {
  type        = string
  description = "Assume Role ARN"
}

variable "assume_role_external_id" {
  type        = string
  description = "Assume Role external ID"
  sensitive   = true
}

variable "storage_standard_ia_days" {
  description = "Number of days to transition objects to STANDARD_IA storage class"
  type        = number
}

variable "storage_glacier_ir_days" {
  description = "Number of days to transition objects to GLACIER_IR storage class"
  type        = number
}

variable "storage_class_standard_ia_name" {
  description = "Storage class for STANDARD_IA"
  type        = string
  default     = "STANDARD_IA"
}
variable "storage_class_glacier_ir_name" {
  description = "Storage class for GLACIER_IR"
  type        = string
  default     = "GLACIER_IR"
}

variable "expiration_processed_days" {
  description = "Number of days after which processed objects expire"
  type        = number  
}

variable "expiration_output_days" {
  description = "Number of days after which output objects expire"
  type        = number
}

variable "expiration_billing_days" {
  description = "Number of days after which billing objects expire"
  type        = number
}

variable "bucket_prefix" {
  description = "Prefix for the S3 bucket"
  type        = string
}

# External bucket configuration
variable "external_bucket_name" {
  description = "Name of the external bucket for job script operations"
  type        = string
  default     = ""
}

variable "external_bucket_account_id" {
  description = "AWS Account ID that owns the external bucket (leave empty if same account)"
  type        = string
  default     = ""
}

variable "enable_cross_account_access" {
  description = "Enable cross-account access features for external bucket"
  type        = bool
  default     = false
}

variable "external_bucket_external_id" {
  description = "External ID for cross-account role assumption (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "external_role_to_replication" {
  description = "ARN of the external IAM role that will be used for S3 replication from external bucket to source bucket"
  type        = string
  default     = ""
}

variable "enable_force_destroy" {
  description = "Enable force destroy for S3 buckets (should be false for production)"
  type        = bool
  default     = false
}

variable "glue_logs" {
  description = "Enable logs for glue"
  type        = bool
  default     = false
}