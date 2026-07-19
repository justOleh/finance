terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "finance-prod-675129110096-tfstate"
    key            = "global/terraform.tfstate"
    region         = "eu-west-1"
    dynamodb_table = "finance-prod-675129110096-tflock"
    encrypt        = true
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

# ---------- Remote state storage ----------

module "tfstate_bucket" {
  source = "./storage/s3"

  buckets = {
    tfstate = {
      name       = local.state_bucket
      versioning = true
    }
  }

  tags = local.common_tags
}

module "tflock_table" {
  source = "./storage/dynamodb"

  tables = {
    tflock = {
      name     = local.lock_table
      hash_key = "LockID"
      attributes = [
        { name = "LockID", type = "S" }
      ]
    }
  }

  tags = local.common_tags
}