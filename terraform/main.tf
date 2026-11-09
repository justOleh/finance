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
    convert_image = {
      name         = "${local.name_prefix}-convert-image"
      force_delete = true
    }
    parse_receipt = {
      name         = "${local.name_prefix}-parse-receipt"
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

# --- Receipt pipeline (ADR-010, ADR-013) --------------------------------------
# Browser --presigned POST--> S3 uploads (any image format)
#   --ObjectCreated--> Lambda convert-image --PNG--> S3 converted
#   --ObjectCreated--> SQS (+ DLQ) --> Lambda parse-receipt --Claude API--> DynamoDB

locals {
  # The queue's visibility timeout must be at least 6 times the consuming function's timeout.
  parse_timeout_seconds = 120
}

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
    # PNGs written by the convert-image Lambda. Browsers never touch it (no CORS). The originals
    # stay in the receipts bucket, so these can be re-created and are expired after a month.
    converted = {
      name            = "${local.name_prefix}-receipts-converted"
      force_destroy   = var.force_destroy_buckets
      expiration_days = 30
    }
  }

  tags = local.common_tags
}

module "receipts_queue" {
  source = "./sqs"

  name = "${local.name_prefix}-receipts"
  # Only the converted bucket sends to the queue (the uploads bucket triggers the Lambda).
  source_bucket_arn          = module.receipts_bucket.bucket_arns["converted"]
  account_id                 = var.aws_account_id
  max_receive_count          = 3
  visibility_timeout_seconds = 6 * local.parse_timeout_seconds

  tags = local.common_tags
}

module "convert_lambda" {
  source = "./convert_lambda"

  name_prefix           = local.name_prefix
  account_id            = var.aws_account_id
  image_repository_url  = module.ecr.repository_urls["convert_image"]
  uploads_bucket_arn    = module.receipts_bucket.bucket_arns["receipts"]
  converted_bucket_arn  = module.receipts_bucket.bucket_arns["converted"]
  converted_bucket_name = module.receipts_bucket.bucket_ids["converted"]

  tags = local.common_tags
}

# One notification configuration per bucket: the uploads bucket triggers the Lambda (it used to
# send to SQS, ADR-010) and the converted bucket sends to the queue.
resource "aws_s3_bucket_notification" "uploads" {
  bucket = module.receipts_bucket.bucket_ids["receipts"]

  lambda_function {
    lambda_function_arn = module.convert_lambda.function_arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "receipts/"
  }

  # S3 validates it may invoke the function when this is created: the permission must exist first.
  depends_on = [module.convert_lambda]
}

resource "aws_s3_bucket_notification" "converted" {
  bucket = module.receipts_bucket.bucket_ids["converted"]

  queue {
    queue_arn     = module.receipts_queue.queue_arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "receipts/"
  }

  # S3 validates it may send to the queue when this is created: the policy must exist first.
  depends_on = [module.receipts_queue]
}

module "parse_lambda" {
  source = "./parse_lambda"

  name_prefix          = local.name_prefix
  image_repository_url = module.ecr.repository_urls["parse_receipt"]
  queue_arn            = module.receipts_queue.queue_arn
  converted_bucket_arn = module.receipts_bucket.bucket_arns["converted"]
  dynamodb_table_arns  = values(module.dynamodb_table.table_arns)
  timeout_seconds      = local.parse_timeout_seconds
  maximum_concurrency  = var.parse_max_concurrency

  # ANTHROPIC_API_KEY is deliberately not here: set it in the Lambda console (see the module).
  environment = {
    ENGINE              = "claude"
    CLAUDE_MODEL        = var.claude_model
    CLAUDE_EFFORT       = var.claude_effort
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