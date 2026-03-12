variable "function_scope" {
  description = "The scope of the Lambda function"
  type        = string
}

variable "prefix" {
  description = "The prefix to use for naming resources"
  type        = string
  
}

variable "handler" {
  description = "The function entrypoint in your code"
  type        = string
}

variable "lambda_environment" {
  description = "Environment variables to pass to the Lambda function"
  type        = object({
    variables = map(string)
  })
  default     = {
    variables = {}
  }
}

variable "policy_documents" {
  description = "Policy statements to attach to the Lambda function"
  type        = list(string) 
  default     = []
}

variable "publish" {
  description = "Whether to publish a new version of the Lambda function"
  type        = bool
  default     = true
}

variable "allowed_triggers" {
  description = "Triggers that are allowed to invoke the Lambda function"
  type        = list(string)
  default     = []
}

variable "runtime" {
  description = "The runtime environment for the Lambda function"
  type        = string
  default     = "python3.11"
}

variable "cloudwatch_logs_retention_in_days" {
  description = "The number of days to retain CloudWatch logs for the Lambda function"
  type        = number
  default     = 365
}

variable "memory_size" {
  description = "The amount of memory available to the Lambda function"
  type        = number
  default     = 1024
}

variable "timeout" {
  description = "The amount of time in seconds that Lambda allows a function to run before stopping it"
  type        = number
  default     = 30
}

variable "ssm_parameter_names" {
  description = "SSM parameter names to pass to the Lambda function"
  type        = list(string)
  default     = []
}

variable "source_dir" {
  description = "Path to the raw Lambda code (relative to root module)"
  type        = string
}

# make your existing filename override optional
variable "file_name" {
  description = "Pre-built ZIP path; if empty, we'll auto-package"
  type        = string
  default     = ""
}

variable "role" {
  description = "IAM role to associate with the Lambda function"
  type        = string
  default     = null
}