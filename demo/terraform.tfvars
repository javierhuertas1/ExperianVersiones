stage = "stg"
aws_region = "us-east-1"
app_id = "27396"
cost_string = "1730.PE.100.402018"
storage_standard_ia_days = 30
storage_glacier_ir_days = 60
expiration_processed_days = 90
expiration_output_days = 180
expiration_billing_days = 180
bucket_prefix = "ascend-ops"

# External bucket configuration
external_bucket_name = "stg-635758777298-ascend-ops-general-bucket-s3"
external_bucket_account_id = "635758777298"  # Same account, leave empty
enable_cross_account_access = true
external_role_to_replication = "arn:aws:iam::635758777298:role/BURoleFor-stg-635758777298-ascend-ops-ReplicationProcessRole"

# S3 bucket force destroy configuration
enable_force_destroy = true  # Set to true for dev/test environments to allow bucket deletion with objects
glue_logs = true