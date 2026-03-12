output "role_arn" {
  description = "ARN of the created IAM role"
  value       = module.iam_role.role_arn
}

output "role_name" {
  description = "Name of the created IAM role"
  value       = module.iam_role.role_name
}

output "policy_arn" {
  description = "ARN of the created IAM policy"
  value       = try(module.iam_role.role_policy, null)
}

output "policy_name" {
  description = "Name of the created IAM policy"
  value       = var.policy_name
}
