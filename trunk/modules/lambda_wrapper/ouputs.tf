output "function_name" {
  description = "Name of lambda function"
  value = module.lambda_wrapper.function_name
}

output "lambda_function_arn" {
  description = "ARN of lambda function"
  value = module.lambda_wrapper.arn
}

output "lambda_function_invoke_arn" {
  description = "ID of lambda function"
  value = module.lambda_wrapper.invoke_arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch log group for the Lambda function"
  value = module.lambda_wrapper.cloudwatch_log_group_name
}

output "role_arn" {
  description = "ARN of the IAM role associated with the Lambda function"
  value = module.lambda_wrapper.role_arn
}

output "role_name" {
  description = "Name of the IAM role associated with the Lambda function"
  value = module.lambda_wrapper.role_name
}

output "qualified_arn" {
  description = "Qualified ARN of the Lambda function"
  value = module.lambda_wrapper.qualified_arn
}