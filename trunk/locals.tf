locals {
  account_id = data.aws_caller_identity.current.account_id
  prefix     = "pe-ascnd-${var.stage}"
  folder_suffixes = [
    "entradas",
    "procesados",
    "salidas",
    "facturacion",
  ]

  config_keys = [
    "entry",
    "processed",
    "output",
    "invoice"
  ]

  config_map = zipmap(local.config_keys, local.folder_suffixes)
  
  # External bucket configuration
  external_account_id = var.external_bucket_account_id != "" ? var.external_bucket_account_id : local.account_id
  external_bucket_arn = var.external_bucket_name != "" ? "arn:aws:s3:::${var.external_bucket_name}" : ""
  is_cross_account = var.enable_cross_account_access && var.external_bucket_account_id != "" && var.external_bucket_account_id != local.account_id
  external_role_to_replication = var.external_role_to_replication != "" ? var.external_role_to_replication : ""

  ## Glue job name
  glue_job_name = "${replace(local.prefix, "-", "_")}_data_processing_job"
}