# =============================================================================
# IAM Wrapper Module - Pinned to specific EITS IAM module version
# =============================================================================

module "iam_role" {
  source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-iam?ref=1.7.1"

  role_name          = var.role_name
  role_description   = var.role_description
  policy_name        = var.policy_name
  policy_description = var.policy_description

  assume_role_policy  = var.assume_role_policy
  policy_documents    = var.policy_documents
  managed_policy_arns = var.managed_policy_arns
}
