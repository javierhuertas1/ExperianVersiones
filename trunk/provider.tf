provider "aws" {
  region = "${var.aws_region}"
  default_tags {
    tags = {
      "Environment" = var.stage
      "AppID"       = var.app_id
      "CostString"  = var.cost_string
    }
  }
  assume_role {
    role_arn     = var.assume_role_arn
    external_id  = var.assume_role_external_id
    session_name = "terraform"
  }
}

terraform {
    required_version = ">= 1.8"
    required_providers {
        aws = {
        source  = "hashicorp/aws"
        version = ">= 5.55"
        }
    }
}