terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "./terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  # Safety: fail if credentials point to the wrong account.
  allowed_account_ids = [var.aws_account_id]
}

locals {
  name_prefix  = "${var.project}-${var.env}-${var.aws_account_id}"
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

module "backend_iam" {
  source = "./iam"

  name_prefix         = local.name_prefix
  dynamodb_table_arns = values(module.dynamodb_table.table_arns)

  local_dev_principal_arns = var.local_dev_principal_arns
  tags                = local.common_tags
}

module "ecr" {
  source = "./ecr"

  repositories = {
    backend = {
      name         = "${local.name_prefix}-backend"
      force_delete = true # learning env: allow destroy even if images exist
    }
  }

  tags = local.common_tags
}

module "backend_ecs" {
  source = "./ecs"

  name_prefix          = local.name_prefix
  image_repository_url = module.ecr.repository_urls["backend"]
  aws_region    = var.aws_region
  task_role_arn = module.backend_iam.backend_role_arn
  allowed_cidr  = var.backend_allowed_cidr
  desired_count = var.backend_desired_count

  environment = {
    AWS_REGION          = var.aws_region
    DYNAMODB_TABLE_NAME = module.dynamodb_table.table_names["app"]
    # Browser origin allowed by CORS: the S3 website hosting the frontend.
    CORS_ORIGINS = module.frontend_bucket.website_urls["app"]
  }

  tags = local.common_tags
}

module "dynamodb_table" {
  source = "./storage/dynamodb"

  tables = {
    app = {
      name      = "${local.name_prefix}-app"
      hash_key  = "pk"
      range_key = "sk"
      attributes = [
        { name = "pk", type = "S" },
        { name = "sk", type = "S" },
        { name = "gsi1pk", type = "S" },
        { name = "gsi1sk", type = "S" },
      ]
      # Access pattern: list expenses by date. gsi1pk is a constant ("EXPENSES"),
      # gsi1sk is "<yyyy-mm-dd>#<id>" so a date range is a single Query.
      global_secondary_indexes = [
        { name = "gsi1", hash_key = "gsi1pk", range_key = "gsi1sk" },
      ]
    }
  }

  tags = local.common_tags
}