# =============================================================================
# IAM CONFIGURATION FOR EXTERNAL BUCKET OPERATIONS
# =============================================================================
# This file contains IAM roles, policies, and bucket policies required for:
# 1. Job Script Execution (Glue/Lambda) - Access to external, source, and Glue buckets
# 2. S3 Replication Service - Cross-region/cross-account replication capabilities
# 3. Cross-Account Access - Bucket policies for external account permissions
# =============================================================================

# =============================================================================
# 1. JOB SCRIPT EXECUTION ROLE (Glue/Lambda)
# =============================================================================

# Trust policy - allows Glue and Lambda services to assume this role
# Also supports cross-account access when external account is different
data "aws_iam_policy_document" "job_script_execution_assume_role" {
  count = var.external_bucket_name != "" ? 1 : 0

  statement {
    sid    = "AssumeRoleGlueLambda"
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type = "Service"
      identifiers = [
        "glue.amazonaws.com",
        "lambda.amazonaws.com"
      ]
    }
  }

  # Add cross-account assume role statement if enabled
  dynamic "statement" {
    for_each = local.is_cross_account ? [1] : []
    content {
      sid    = "AssumeRoleCrossAccount"
      effect = "Allow"
      actions = [
        "sts:AssumeRole"
      ]

      principals {
        type        = "AWS"
        identifiers = ["arn:aws:iam::${local.external_account_id}:root"]
      }
    }
  }
}

# Permissions policy - defines what the job scripts can do
data "aws_iam_policy_document" "external_bucket_access" {
  count = var.external_bucket_name != "" ? 1 : 0

  statement {
    sid    = "ExternalBucketFullAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:PutObjectAcl",
      "s3:GetObjectAcl",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts"
    ]
    resources = [
      local.external_bucket_arn,
      "${local.external_bucket_arn}/*"
    ]
  }

  statement {
    sid    = "SourceBucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]
    resources = [
      module.source_bucket.s3_bucket_arn,
      "${module.source_bucket.s3_bucket_arn}/*"
    ]
  }

  statement {
    sid    = "GlueScriptsBucketAccess"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:ListBucket",
      "s3:GetBucketLocation"
    ]
    resources = [
      module.glue_scripts_bucket.s3_bucket_arn,
      "${module.glue_scripts_bucket.s3_bucket_arn}/*"
    ]
  }

  statement {
    sid    = "CloudWatchLogsAccess"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]
    resources = ["arn:aws:logs:*:*:*"]
  }
}

# IAM Role creation using EITS wrapper module
module "job_script_execution_role" {
  count  = var.external_bucket_name != "" ? 1 : 0
  source = "./modules/iam_wrapper"

  role_name          = "${local.prefix}-job-script-execution-role"
  role_description   = "Allow job scripts (Glue/Lambda) to perform operations on both external and source buckets"
  policy_name        = "${local.prefix}-job-script-execution-policy"
  policy_description = "Policy for job scripts to access external and source buckets with CloudWatch logging"

  assume_role_policy = data.aws_iam_policy_document.job_script_execution_assume_role[0].json
  policy_documents   = [data.aws_iam_policy_document.external_bucket_access[0].json]
  
  # Add managed policies for Glue service role
  managed_policy_arns = [
    "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
  ]
}

# =============================================================================
# 2. S3 REPLICATION SERVICE ROLE
# =============================================================================

# Trust policy - allows S3 service to assume this role for replication
data "aws_iam_policy_document" "s3_replication_assume_role" {
  count = var.external_bucket_name != "" ? 1 : 0

  statement {
    sid    = "AssumeRoleS3Service"
    effect = "Allow"
    actions = [
      "sts:AssumeRole"
    ]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }
  }
}

# Permissions policy - defines replication permissions for source and destination buckets
data "aws_iam_policy_document" "s3_replication_access" {
  count = var.external_bucket_name != "" ? 1 : 0

  statement {
    sid    = "ReplicationSourcePermissions"
    effect = "Allow"
    actions = [
      "s3:GetObjectVersionForReplication",
      "s3:GetObjectVersionAcl",
      "s3:ListBucket",
      "s3:GetBucketVersioning",
      "s3:GetReplicationConfiguration",
      "s3:GetObjectVersionTagging"
    ]
    resources = [
      local.external_bucket_arn,
      "${local.external_bucket_arn}/*",
      local.external_role_to_replication
    ]
  }

  statement {
    sid    = "ReplicationDestinationPermissions"
    effect = "Allow"
    actions = [
      "s3:ReplicateObject",
      "s3:ReplicateDelete",
      "s3:ReplicateTags",
      "s3:GetBucketVersioning"
    ]
    resources = [
      module.source_bucket.s3_bucket_arn,
      "${module.source_bucket.s3_bucket_arn}/*"
    ]
  }
}

# IAM Role creation using EITS wrapper module
module "s3_replication_role" {
  count  = var.external_bucket_name != "" ? 1 : 0
  source = "./modules/iam_wrapper"

  role_name          = "${local.prefix}-s3-replication-role"
  role_description   = "Allow S3 replication service to replicate from external bucket to source bucket"
  policy_name        = "${local.prefix}-s3-replication-policy"
  policy_description = "Policy for S3 replication from external bucket to source bucket"

  assume_role_policy = data.aws_iam_policy_document.s3_replication_assume_role[0].json
  policy_documents   = [data.aws_iam_policy_document.s3_replication_access[0].json]
}

# =============================================================================
# 3. CROSS-ACCOUNT BUCKET POLICIES
# =============================================================================

# Bucket policy for source bucket - allows external replication role access
# This policy enables the external replication role (from terraform.tfvars) to perform 
# S3 replication operations on the destination (source) bucket, following AWS best practices
# for cross-account or external bucket replication scenarios
resource "aws_s3_bucket_policy" "source_bucket_cross_account_policy" {
  count = var.external_bucket_name != "" ? 1 : 0
  
  bucket = module.source_bucket.s3_bucket_id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowReplicationFromOriginRole"
        Effect = "Allow"
        Principal = {
          AWS = var.external_role_to_replication != "" ? var.external_role_to_replication : module.s3_replication_role[0].role_arn
        }
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
          "s3:GetObjectVersionTagging",
          "s3:ObjectOwnerOverrideToBucketOwner",
          "s3:PutObject"
        ]
        Resource = [
          module.source_bucket.s3_bucket_arn,
          "${module.source_bucket.s3_bucket_arn}/*"
        ]
      }
    ]
  })
}
