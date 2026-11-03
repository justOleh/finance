terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  # Safety: fail if credentials point to the wrong account.
  allowed_account_ids = [var.aws_account_id]
}

locals {
  name_prefix  = "${var.project}-${var.env}-${var.aws_account_id}"
  state_bucket = "${local.name_prefix}-tfstate"
  lock_table   = "${local.name_prefix}-tflock"
  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
  }
}


module "frontend_bucket" {
  source = "./storage/s3"

  buckets = {
    app = {
      name              = "${local.name_prefix}-frontend"
      versioning        = true
      website_hosting   = true
      index_document    = "index.html"
      error_document    = "index.html"
      block_public      = false
    }
  }

  tags = local.common_tags
}

# ---------- Outputs ----------

output "frontend_bucket_id" {
  description = "Frontend S3 bucket ID"
  value       = module.frontend_bucket.bucket_ids["app"]
}

output "frontend_bucket_endpoint" {
  description = "Frontend S3 bucket website endpoint"
  value       = module.frontend_bucket.bucket_endpoints["app"]
}