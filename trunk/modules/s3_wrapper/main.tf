# =============================================================================
# S3 Wrapper Module - Pinned to specific EITS S3 module version
# =============================================================================

module "s3_bucket" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-s3.git?ref=2.13.1"

  bucket_name        = var.bucket_name
  versioning_enabled = var.versioning_enabled
  lifecycle_rules    = var.lifecycle_rules
  
  # Security defaults
  force_destroy = var.force_destroy
  
  # Optional configurations
  bucket_policy           = var.bucket_policy
  source_policy_documents = var.source_policy_documents
  
  # Encryption
  sse_algorithm = var.sse_algorithm
  kms_key_arn   = var.kms_key_arn
  
  # Access control
  object_ownership = var.object_ownership
  
  # Intelligent tiering
  intelligent_tiering = var.intelligent_tiering
  
}
