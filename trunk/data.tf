data "aws_caller_identity" "current" {
  # This data source retrieves the AWS account ID of the current user
  # and is used to set the account_id local variable.
}