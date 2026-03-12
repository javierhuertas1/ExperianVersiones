variable "name" {
  description = "Name of the SSM parameter"
  type        = string
}

variable "value" {
  description = "Value of the SSM parameter"
  type        = string
}

variable "description" {
  description = "Description of the SSM parameter"
  type        = string
  default     = ""
}

variable "type" {
  description = "Type of the SSM parameter (String, StringList, SecureString)"
  type        = string
  default     = "String"
}

variable "tier" {
  description = "Parameter tier (Standard, Advanced, Intelligent-Tiering)"
  type        = string
  default     = "Standard"
}

variable "key_id" {
  description = "KMS key ID for SecureString parameters"
  type        = string
  default     = null
}
