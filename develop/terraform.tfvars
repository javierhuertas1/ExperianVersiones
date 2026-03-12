stage = "dev"
aws_region = "us-east-1"
app_id = "27396"
cost_string = "1730.PE.100.402018"
storage_standard_ia_days = 30
storage_glacier_ir_days = 61
expiration_processed_days = 90
expiration_output_days = 181
expiration_billing_days = 181
bucket_prefix = "ascend-ops"

# External bucket configuration
external_bucket_name = "dev-214982159444-ascend-ops-general-bucket-s3"
external_bucket_account_id = "214982159444"  # Same account, leave empty
enable_cross_account_access = true
external_role_to_replication = "arn:aws:iam::214982159444:role/BURoleFor-dev-214982159444-ascend-ops-ReplicationProcessRole"
# S3 bucket force destroy configuration
enable_force_destroy = true  # Set to true for dev/test environments to allow bucket deletion with objects