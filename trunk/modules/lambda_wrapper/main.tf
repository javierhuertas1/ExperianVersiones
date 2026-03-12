module "lambda_wrapper" {
    source = "git::https://code.experian.local/scm/EUCES/eits-tf-aws-lambda.git?ref=1.7.1"

    function_scope      = var.function_scope
    filename            = local.zip_path
    source_code_hash    = local.source_code_hash
    handler             = var.handler
    runtime             = var.runtime

    lambda_environment  = var.lambda_environment
    prefix              = var.prefix
    role                = var.role
    policy_documents    = var.policy_documents
    publish             = var.publish
    cloudwatch_logs_retention_in_days = var.cloudwatch_logs_retention_in_days
    ssm_parameter_names = var.ssm_parameter_names

    memory_size         = var.memory_size 
    timeout             = var.timeout 
}