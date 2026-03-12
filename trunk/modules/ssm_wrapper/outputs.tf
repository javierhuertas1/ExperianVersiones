output "parameter_name" {
  description = "Name of the created SSM parameter"
  value       = module.ssm_parameter.ssm_parameter_name
}

output "parameter_arn" {
  description = "ARN of the created SSM parameter"
  value       = module.ssm_parameter.ssm_parameter_arn
}

output "parameter_value" {
  description = "Value of the created SSM parameter"
  value       = module.ssm_parameter.parameter_value
  sensitive   = true
}

output "parameter_version" {
  description = "Version of the created SSM parameter"
  value       = module.ssm_parameter.ssm_parameter_version
}
