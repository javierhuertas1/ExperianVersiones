# =============================================================================
# S3 Buckets Configuration
# =============================================================================

# Separate bucket for storing Glue scripts and artifacts
module "glue_scripts_bucket" {
  source = "./modules/s3_wrapper"

  bucket_name        = join("-", [local.prefix, local.account_id, "glue-scripts-bucket"])
  versioning_enabled = true
  force_destroy      = var.enable_force_destroy

}

# Main data processing bucket
module "source_bucket" {
  source = "./modules/s3_wrapper"

  bucket_name        = join("-", [local.prefix, local.account_id, "bucket"])
  versioning_enabled = true
  force_destroy      = var.enable_force_destroy

  lifecycle_rules = [
    # ============================================
    # 1) Procesados
    {
      id     = "${local.prefix}-lc-procesados"
      status = "Enabled"

      # match on the `S3Stage=procesados` tag
      filter = {
        prefix = "${var.bucket_prefix}/procesados"
      }

      transition = [
        { days     = var.storage_standard_ia_days,  storage_class = var.storage_class_standard_ia_name },
        { days     = var.storage_glacier_ir_days,  storage_class = var.storage_class_glacier_ir_name },
      ]

      expiration = {
        days = var.expiration_processed_days
      }
    },

    # ============================================
    # 2) Salidas
    {
      id     = "${local.prefix}-lc-salidas"
      status = "Enabled"

      filter = {
        prefix = "${var.bucket_prefix}/salidas"
      }

      transition = [
        { days     = var.storage_standard_ia_days,  storage_class = var.storage_class_standard_ia_name },
        { days     = var.storage_glacier_ir_days,  storage_class = var.storage_class_glacier_ir_name },
      ]

      expiration = {
        days = var.expiration_processed_days
      }
    },

    # ============================================
    # 3) Facturación
    {
      id     = "${local.prefix}-lc-facturacion"
      status = "Enabled"

      filter = {
        prefix = "${var.bucket_prefix}/facturacion"
      }

      transition = [
        { days     = var.storage_standard_ia_days,  storage_class = var.storage_class_standard_ia_name },
        { days     = var.storage_glacier_ir_days,  storage_class = var.storage_class_glacier_ir_name },
      ]

      expiration = {
        days = var.expiration_billing_days
      }
    },
  ]
}

resource "aws_lambda_permission" "allow_s3_invoke" {
  statement_id  = "${local.prefix}-AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = module.job-launcher.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = module.source_bucket.s3_bucket_arn
}

resource "aws_lambda_permission" "allow_s3_invoke_invoice" {
  statement_id  = "${local.prefix}-AllowExecutionFromS3Invoice"
  action        = "lambda:InvokeFunction"
  function_name = module.start-invoice-process.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = module.source_bucket.s3_bucket_arn
}

resource "aws_lambda_permission" "allow_s3_invoke_output_mover" {
  statement_id  = "${local.prefix}-AllowExecutionFromS3OutputMover"
  action        = "lambda:InvokeFunction"
  function_name = module.output-mover.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = module.source_bucket.s3_bucket_arn
}

resource "aws_s3_bucket_notification" "on_upload_file" {
  bucket = module.source_bucket.s3_bucket_id

  lambda_function {
    lambda_function_arn = module.job-launcher.lambda_function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "${var.bucket_prefix}/entradas/"
  }
  lambda_function {
    lambda_function_arn = module.start-invoice-process.lambda_function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "${var.bucket_prefix}/salidas/"
    filter_suffix       = ".log"
  }
  lambda_function {
    lambda_function_arn = module.output-mover.lambda_function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "output/peru/"
    filter_suffix       = ".log"
  }

  depends_on = [
    aws_lambda_permission.allow_s3_invoke,
    aws_lambda_permission.allow_s3_invoke_invoice,
    aws_lambda_permission.allow_s3_invoke_output_mover,
    aws_s3_object.bucket_folder
  ]
}

resource "aws_s3_object" "bucket_folder" {
  for_each = toset(local.folder_suffixes)

  bucket     = module.source_bucket.s3_bucket_id
  key        = "${var.bucket_prefix}/${each.value}/"

  # ensure the bucket itself exists first
  depends_on = [ module.source_bucket ]
}

# Upload Glue script to dedicated scripts bucket
resource "aws_s3_object" "glue_entry_job_script" {
  bucket = module.glue_scripts_bucket.s3_bucket_id
  key    = "scripts/glue_entry_job.py"
  source = "${path.root}/../glue_scripts/glue_entry_job.py"
  etag   = filemd5("${path.root}/../glue_scripts/glue_entry_job.py")

  depends_on = [ 
    module.glue_scripts_bucket
  ]
}