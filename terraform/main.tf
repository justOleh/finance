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
      name            = "${local.name_prefix}-frontend"
      versioning      = true
      website_hosting = true
      index_document  = "index.html"
      error_document  = "index.html"
      block_public    = false
      force_destroy   = var.force_destroy_buckets
    }
  }

  tags = local.common_tags
}

module "registry" {
  source = "./registry/ecr"

  repositories = {
    backend = "${local.name_prefix}-backend"
    parser  = "${local.name_prefix}-parser"
  }
  tags = local.common_tags
}

module "database" {
  source = "./storage/dynamodb"

  tables = {
    expenses = {
      name     = "${local.name_prefix}-expenses"
      hash_key = "id"
      attributes = [
        { name = "id", type = "S" },
      ]
    }
  }
  tags = local.common_tags
}

module "backend" {
  source = "./compute/backend"

  name_prefix          = local.name_prefix
  image_repository_url = module.registry.repository_urls["backend"]
  dynamodb_table_arns  = values(module.database.table_arns)
  environment = {
    RECEIPTS_DIR       = "./data/receipts"
    RECEIPT_PARSER_URL = "http://${module.parser.alb_dns_name}"
    AWS_REGION         = var.aws_region
    DYNAMODB_TABLE     = module.database.table_names["expenses"]
  }
  tags = local.common_tags
}

module "parser" {
  source = "./compute/backend"

  name_prefix          = local.name_prefix
  service_name         = "parser"
  cluster_suffix       = "parser-cluster"
  alb_suffix           = "prs"
  image_repository_url = module.registry.repository_urls["parser"]
  cpu                  = var.parser_cpu
  memory               = var.parser_memory
  tags                 = local.common_tags
}

# ---------- Outputs ----------

output "backend_ecr_repository_url" {
  value = module.registry.repository_urls["backend"]
}

output "backend_cluster_name" {
  value = module.backend.cluster_name
}

output "backend_service_name" {
  value = module.backend.service_name
}

output "frontend_bucket_id" {
  description = "Frontend S3 bucket ID"
  value       = module.frontend_bucket.bucket_ids["app"]
}

output "frontend_bucket_endpoint" {
  description = "Frontend S3 bucket website endpoint"
  value       = module.frontend_bucket.bucket_endpoints["app"]
}
output "backend_url" {
  description = "Stable backend URL (ALB)"
  value       = "http://${module.backend.alb_dns_name}"
}

output "parser_ecr_repository_url" {
  value = module.registry.repository_urls["parser"]
}

output "parser_cluster_name" {
  value = module.parser.cluster_name
}

output "parser_service_name" {
  value = module.parser.service_name
}
