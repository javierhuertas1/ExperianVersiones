module "job-launcher" {
  source            = "./modules/lambda_wrapper"
  source_dir        = "${path.module}/../functions/job-launcher/src"
  function_scope    = "job-launcher"
  handler           = "index.handler"
  prefix            = local.prefix
  timeout           = 60
  lambda_environment = {
    variables = {
      GLUE_JOB_NAME = local.glue_job_name
      ASCEND_OPS_BASE_PARAMETER_STORE = "/${var.bucket_prefix}/${var.stage}"
      ASCEND_OPS_BASE_BUCKET = var.bucket_prefix
    }
  }
  policy_documents  = [
    data.aws_iam_policy_document.job_launcher_lambda_policy.json
  ]
}

####################################################
# 1. IAM inline policy for the job-launcher Lambda #
################################################### \#

data "aws_iam_policy_document" "job_launcher_lambda_policy" {
  # Include reusable SSM policy
  source_policy_documents = [
    data.aws_iam_policy_document.ssm_parameter_access_policy.json,
    data.aws_iam_policy_document.s3_bucket_access_policy.json
  ]
  statement {
    sid = "AllowStartGlueJob"
    effect    = "Allow"
    actions   = [
      "glue:StartJobRun",
      "glue:GetJobRun",
      "glue:GetJobRuns"
    ]

    resources = [
      "arn:aws:glue:*:${local.account_id}:job/${replace(local.prefix, "-", "_")}_*"
    ]
  }

  # Optional: Allow Lambda to assume the job script execution role for external bucket access
  dynamic "statement" {
    for_each = var.external_bucket_name != "" ? [1] : []
    content {
      sid = "AllowAssumeJobScriptRole"
      effect = "Allow"
      actions = [
        "sts:AssumeRole"
      ]
      resources = [
        module.job_script_execution_role[0].role_arn
      ]
    }
  }
  
}

# =============================================================================
# Invoice Processing Lambda Functions
# =============================================================================

# Start Invoice Process Lambda
module "start-invoice-process" {
  source            = "./modules/lambda_wrapper"
  source_dir        = "${path.module}/../functions/start-invoice-process/src"
  function_scope    = "start-invoice-process"
  handler           = "index.handler"
  prefix            = local.prefix
  timeout           = 30
  lambda_environment = {
    variables = {
      SQS_QUEUE_URL = module.invoice_processing_queue.queue_url
      ASCEND_OPS_BASE_PARAMETER_STORE = "/${var.bucket_prefix}/${var.stage}"
      ASCEND_OPS_BASE_BUCKET = var.bucket_prefix
    }
  }
  policy_documents  = [
    data.aws_iam_policy_document.start_invoice_process_lambda_policy.json
  ]
}

# Invoice Generation Lambda
module "invoice-generation" {
  source            = "./modules/lambda_wrapper"
  source_dir        = "${path.module}/../functions/invoice-generation/src"
  function_scope    = "invoice-generation"
  handler           = "index.handler"
  prefix            = local.prefix
  timeout           = 300  # 5 minutes for CSV processing
  lambda_environment = {
    variables = {
      ASCEND_OPS_BASE_BUCKET = var.bucket_prefix
    }
  }
  policy_documents  = [
    data.aws_iam_policy_document.invoice_generation_lambda_policy.json
  ]
}

# Event Source Mapping for SQS to Lambda
resource "aws_lambda_event_source_mapping" "invoice_queue_trigger" {
  event_source_arn = module.invoice_processing_queue.queue_arn
  function_name    = module.invoice-generation.lambda_function_arn
  batch_size       = 1  # Process one message at a time for FIFO ordering
  enabled          = true

  depends_on = [
    module.invoice-generation
  ]
}

# =============================================================================
# IAM Policies for Invoice Processing Lambdas
# =============================================================================

# Policy for start-invoice-process Lambda (reuse existing policies)
data "aws_iam_policy_document" "start_invoice_process_lambda_policy" {
  # Include reusable SSM policy
  source_policy_documents = [
    data.aws_iam_policy_document.ssm_parameter_access_policy.json
  ]

  # Add SQS permissions for sending messages
  statement {
    sid       = "AllowSQSAccess"
    effect    = "Allow"
    actions   = [
      "sqs:SendMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [
      module.invoice_processing_queue.queue_arn
    ]
  }
}

# Policy for invoice-generation Lambda (reuse existing policies)
data "aws_iam_policy_document" "invoice_generation_lambda_policy" {
  # Include reusable SSM and S3 policies
  source_policy_documents = [
    data.aws_iam_policy_document.ssm_parameter_access_policy.json,
    data.aws_iam_policy_document.s3_bucket_access_policy.json
  ]

  # Add SQS permissions for receiving and deleting messages
  statement {
    sid       = "AllowSQSReceiveAndDelete"
    effect    = "Allow"
    actions   = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
    ]
    resources = [
      module.invoice_processing_queue.queue_arn
    ]
  }
}

# Policy for output-mover Lambda (reuse existing policies)
data "aws_iam_policy_document" "output_mover_lambda_policy" {
  # Include reusable SSM and S3 policies
  source_policy_documents = [
    data.aws_iam_policy_document.ssm_parameter_access_policy.json,
    data.aws_iam_policy_document.s3_bucket_access_policy.json
  ]
}

# Output to Salidas File Moving Lambda (for replication output processing)
module "output-mover" {
  source            = "./modules/lambda_wrapper"
  source_dir        = "${path.module}/../functions/output-mover/src"
  function_scope    = "output-mover"
  handler           = "index.handler"
  prefix            = local.prefix
  timeout           = 60
  lambda_environment = {
    variables = {
      ASCEND_OPS_BASE = "/${var.bucket_prefix}"
      BUCKET_NAME     = module.source_bucket.s3_bucket_id
    }
  }
  policy_documents  = [
    data.aws_iam_policy_document.output_mover_lambda_policy.json
  ]
}

# =============================================================================
# Reusable Policy Data Sources (to avoid duplication)
# =============================================================================

# SSM Parameter Store access policy (reusable)
data "aws_iam_policy_document" "ssm_parameter_access_policy" {
  statement {
    sid       = "AllowGetKeysFromParameterStore"
    effect    = "Allow"
    actions   = [
      "ssm:GetParameters",
      "ssm:GetParameter",
      "ssm:GetParametersByPath",
      "ssm:GetParameterHistory"
    ]
    resources = [
      "arn:aws:ssm:*:${local.account_id}:parameter/*"
    ]
  }
}

# S3 bucket access policy (reusable)
data "aws_iam_policy_document" "s3_bucket_access_policy" {
  statement {
    sid = "AllowS3BucketOperations"
    effect    = "Allow"
    actions = [
      "s3:ListBucket",          
      "s3:GetObject",           
      "s3:PutObject",           
      "s3:DeleteObject",        
      "s3:PutObjectTagging",    
      "s3:GetObjectTagging"
    ]
    resources = [
      module.source_bucket.s3_bucket_arn,
      "${module.source_bucket.s3_bucket_arn}/*"
    ]
  }
}

