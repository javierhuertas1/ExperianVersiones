# =============================================================================
# SSM Parameter Store Wrapper Module - Pinned to specific EITS SSM module version
# =============================================================================

module "ssm_parameter" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-ssm-parameter.git?ref=1.3.0"

  name        = var.name
  value       = var.value
  description = var.description
  type        = var.type
  tier        = var.tier
  key_id      = var.key_id
}
