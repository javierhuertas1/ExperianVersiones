variable "bucket_name" {
  description = "The name of the bucket, must be unique"
  type        = string
}

variable "versioning_enabled" {
  description = "Defines whether bucket versioning is enabled or disabled"
  type        = bool
  default     = true
}

variable "lifecycle_rules" {
  description = "A list of maps defining the lifecycle rules for the bucket"
  type = list(object({
    id                                     = optional(string)
    status                                 = optional(string, "Enabled")
    abort_incomplete_multipart_upload_days = optional(number)
    expiration = optional(object({
      date                         = optional(string)
      days                         = optional(number)
      expired_object_delete_marker = optional(bool)
    }))
    filter = optional(object({
      prefix                   = optional(string)
      object_size_greater_than = optional(number)
      object_size_less_than    = optional(number)
      tags                     = optional(map(string), {})
    }), {})
    noncurrent_version_expiration = optional(object({
      newer_noncurrent_versions = optional(number)
      noncurrent_days           = optional(number)
    }))
    noncurrent_version_transition = optional(list(object({
      newer_noncurrent_versions = optional(number)
      noncurrent_days           = optional(number)
      storage_class             = optional(string)
    })), [])
    transition = optional(list(object({
      date          = optional(string)
      days          = optional(number)
      storage_class = optional(string)
    })), [])
  }))
  default = []
}

variable "force_destroy" {
  description = "A boolean that indicates all objects should be deleted from the bucket so that the bucket can be destroyed without error"
  type        = bool
  default     = false
}

variable "bucket_policy" {
  description = "Accepts either a relative path for a bucket policy json file, or direct json"
  type        = string
  default     = null
}

variable "source_policy_documents" {
  description = "List of IAM policy documents (in json) that will be merged together"
  type        = list(any)
  default     = []
}

variable "sse_algorithm" {
  description = "Server-side encryption algorithm to use. Valid values are AES256 or aws:kms"
  type        = string
  default     = "AES256"
}

variable "kms_key_arn" {
  description = "ARN of an existing AWS KMS key. Must be set if sse_algorithm is set to aws:kms"
  type        = string
  default     = null
}

variable "object_ownership" {
  description = "Object ownership. Valid values are BucketOwnerPreferred, ObjectWriter or BucketOwnerEnforced"
  type        = string
  default     = "BucketOwnerEnforced"
}

variable "intelligent_tiering" {
  description = "A map of maps containing intelligent tiering configuration"
  type = map(object({
    status = optional(string, "Enabled")
    filter = optional(object({
      prefix = optional(string)
      tags   = optional(map(string))
    }))
    tiering = optional(map(object({
      days = optional(number)
    })), {})
  }))
  default = {}
}

