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
  name_prefix = "${var.project}-${var.env}-${var.aws_account_id}"
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
  receipts_bucket_arn = module.receipts_bucket.bucket_arns["receipts"]

  local_dev_principal_arns = var.local_dev_principal_arns
  tags                     = local.common_tags
}

module "ecr" {
  source = "./ecr"

  repositories = {
    backend = {
      name         = "${local.name_prefix}-backend"
      force_delete = true # learning env: allow destroy even if images exist
    }
    parser = {
      name         = "${local.name_prefix}-parser"
      force_delete = true
    }
  }

  tags = local.common_tags
}

module "cognito" {
  source = "./cognito"

  name_prefix = local.name_prefix
  tags        = local.common_tags
}

module "backend_ecs" {
  source = "./ecs"

  name_prefix          = local.name_prefix
  image_repository_url = module.ecr.repository_urls["backend"]
  aws_region           = var.aws_region
  task_role_arn        = module.backend_iam.backend_role_arn
  desired_count        = var.backend_desired_count

  environment = {
    AWS_REGION          = var.aws_region
    DYNAMODB_TABLE_NAME = module.dynamodb_table.table_names["app"]
    # Bucket the browser uploads receipts to (presigned POST issued by the backend).
    RECEIPTS_BUCKET = module.receipts_bucket.bucket_ids["receipts"]
    # Browser origin allowed by CORS: the S3 website hosting the frontend.
    CORS_ORIGINS = module.frontend_bucket.website_urls["app"]
    # The backend verifies access tokens issued by this pool/client.
    COGNITO_USER_POOL_ID = module.cognito.user_pool_id
    COGNITO_CLIENT_ID    = module.cognito.client_id
  }

  tags = local.common_tags
}

# --- Receipt upload pipeline (ADR-010) ---------------------------------------
# Browser --presigned POST--> S3 --ObjectCreated--> SQS --> parser worker --> DynamoDB

module "receipts_bucket" {
  source = "./storage/s3"

  buckets = {
    receipts = {
      name          = "${local.name_prefix}-receipts"
      force_destroy = var.force_destroy_buckets
      # Browsers POST straight to S3, so S3 must allow the frontend origin (CORS).
      cors_allowed_origins = [module.frontend_bucket.website_urls["app"]]
      cors_allowed_methods = ["POST"]
    }
  }

  tags = local.common_tags
}

module "receipts_queue" {
  source = "./sqs"

  name              = "${local.name_prefix}-receipts"
  source_bucket_arn = module.receipts_bucket.bucket_arns["receipts"]
  account_id        = var.aws_account_id
  max_receive_count = 3

  tags = local.common_tags
}

resource "aws_s3_bucket_notification" "receipts" {
  bucket = module.receipts_bucket.bucket_ids["receipts"]

  queue {
    queue_arn     = module.receipts_queue.queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "receipts/"
  }

  # S3 validates it may send to the queue when this is created: the policy must exist first.
  depends_on = [module.receipts_queue]
}

module "parser_worker" {
  source = "./worker"

  name_prefix          = local.name_prefix
  aws_region           = var.aws_region
  cluster_arn          = module.backend_ecs.cluster_arn
  image_repository_url = module.ecr.repository_urls["parser"]
  desired_count        = var.parser_desired_count
  queue_arn            = module.receipts_queue.queue_arn
  receipts_bucket_arn  = module.receipts_bucket.bucket_arns["receipts"]
  dynamodb_table_arns  = values(module.dynamodb_table.table_arns)

  environment = {
    AWS_REGION          = var.aws_region
    QUEUE_URL           = module.receipts_queue.queue_url
    DYNAMODB_TABLE_NAME = module.dynamodb_table.table_names["app"]
    MAX_RECEIVE_COUNT   = "3" # keep equal to the queue's maxReceiveCount
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