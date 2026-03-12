# =============================================================================
# Glue Data Processing using EITS Glue Module
# =============================================================================

module "glue_data_processing" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-glue.git?ref=1.3.1"
  
  # Required: Database configuration (minimal - for EITS module compliance only)
  database_name        = replace("${local.prefix}_database", "-", "_")
  database_description = "Minimal Glue catalog database - required by EITS module. Job processes files without catalog operations."

  # IAM Role configuration
  create_service_role = var.external_bucket_name != "" ? false : true
  service_role_arn    = var.external_bucket_name != "" ? module.job_script_execution_role[0].role_arn : null
  service_role_name   = var.external_bucket_name == "" ? "${local.prefix}-glue-service-role" : null
  # CloudWatch logging configuration
  create_cloudwatch_logs = var.glue_logs

  # Glue Jobs configuration
  jobs = {
    "${local.glue_job_name}" = {
      description   = "Data processing job for ${local.prefix} - processes files from entradas folder"
      glue_version  = "4.0"
      worker_type   = "G.1X"
      number_of_workers = 2
      max_retries   = 1
      timeout       = 60

      command = {
        script_location = "s3://${module.glue_scripts_bucket.s3_bucket_id}/scripts/glue_entry_job.py"
        python_version  = "3"
      }

      execution_property = {
        max_concurrent_runs = 5
      }

      default_arguments = {
        "--job-language"                      = "python"
        "--enable-metrics"                    = "true"
        "--enable-continuous-cloudwatch-log"  = "true"
        "--job-bookmark-option"               = "job-bookmark-enable"
        "--external-bucket-name"              = var.external_bucket_name
        "--source-bucket-name"                = module.source_bucket.s3_bucket_id
        "--database-name"                     = replace("${local.prefix}_database", "-", "_")
        "--temp-dir"                          = "s3://${module.glue_scripts_bucket.s3_bucket_id}/temp/"
        "--TempDir"                           = "s3://${module.glue_scripts_bucket.s3_bucket_id}/temp/"
      }
    }
  }
}
