variable "role_name" {
  description = "Name of the IAM role"
  type        = string
}

variable "role_description" {
  description = "Description of the IAM role"
  type        = string
}

variable "policy_name" {
  description = "Name of the IAM policy"
  type        = string
}

variable "policy_description" {
  description = "Description of the IAM policy"
  type        = string
}

variable "assume_role_policy" {
  description = "JSON string of the assume role policy document"
  type        = string
}

variable "policy_documents" {
  description = "List of JSON policy documents to attach to the role"
  type        = list(string)
  default     = []
}

variable "managed_policy_arns" {
  description = "List of managed policy ARNs to attach to the role"
  type        = list(string)
  default     = []
}
