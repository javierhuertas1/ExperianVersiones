output "s3_bucket_id" {
  description = "The name of the bucket"
  value       = module.s3_bucket.s3_bucket_id
}

output "s3_bucket_arn" {
  description = "The ARN of the bucket"
  value       = module.s3_bucket.s3_bucket_arn
}

output "s3_bucket_domain_name" {
  description = "Bucket domain name"
  value       = module.s3_bucket.s3_bucket_domain_name
}

output "s3_bucket_regional_domain_name" {
  description = "The bucket region-specific domain name"
  value       = module.s3_bucket.s3_bucket_regional_domain_name
}

output "s3_region" {
  description = "AWS region this bucket resides in"
  value       = module.s3_bucket.s3_region
}

output "replication_iam_role_arn" {
  description = "ARN for the IAM role created for replication configuration"
  value       = module.s3_bucket.replication_iam_role_arn
}
