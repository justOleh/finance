terraform {
  required_version = ">= 1.5.7"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
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

  cognito_issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${module.cognito.user_pool_id}"

  # Browser origins allowed to call the API and to POST receipts to S3: the CloudFront site,
  # plus anything listed for local frontend development (for example http://localhost:5173).
  browser_origins = concat([module.cdn.url], var.extra_cors_origins)
  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "terraform"
  }
}


module "frontend_bucket" {
  source = "./storage/s3"

  buckets = {
    # Private: only CloudFront reads it (module.cdn adds the bucket policy). ADR-014.
    app = {
      name          = "${local.name_prefix}-frontend"
      versioning    = true
      force_destroy = var.force_destroy_buckets
    }
  }

  tags = local.common_tags
}

# The frontend bucket used to be a public S3 website (ADR-007). Its public-read policy and website
# configuration were resources of the s3 module, which no longer has them (ADR-014).
# `destroy = false` makes Terraform forget the old policy instead of deleting it: module.cdn then
# overwrites it with the CloudFront-only policy. A delete could run after that write and remove
# the new policy, because Terraform does not order the two. (A `moved` block would also work, but
# it breaks the `-target=module.ecr` step of deploy.sh.) Safe to delete after the first apply.
removed {
  from = module.frontend_bucket.aws_s3_bucket_policy.public_read

  lifecycle {
    destroy = false
  }
}

# HTTPS for the site; the S3 website endpoint (HTTP only, public bucket) is gone.
module "cdn" {
  source = "./cdn"

  name_prefix                 = local.name_prefix
  bucket_id                   = module.frontend_bucket.bucket_ids["app"]
  bucket_arn                  = module.frontend_bucket.bucket_arns["app"]
  bucket_regional_domain_name = module.frontend_bucket.bucket_regional_domain_names["app"]

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
    agent = {
      name         = "${local.name_prefix}-agent"
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
    # Browser origins allowed by CORS. API Gateway answers CORS itself (module.backend_api);
    # this keeps the backend consistent if it is ever called directly.
    CORS_ORIGINS = join(",", local.browser_origins)
    # The backend verifies access tokens issued by this pool/client.
    COGNITO_USER_POOL_ID = module.cognito.user_pool_id
    COGNITO_CLIENT_ID    = module.cognito.client_id
  }

  tags = local.common_tags
}

# --- HTTPS front door and chat agent (ADR-014) ---------------------------------
# Browser --> HTTP API (TLS, Cognito JWT, throttling) --VPC link--> Cloud Map --> backend task
# Browser --> AgentCore Runtime (Cognito JWT) --> agent --> the same HTTP API, same token

module "backend_api" {
  source = "./api_gateway"

  name_prefix               = local.name_prefix
  vpc_id                    = module.backend_ecs.vpc_id
  subnet_ids                = module.backend_ecs.subnet_ids
  backend_security_group_id = module.backend_ecs.security_group_id
  backend_port              = module.backend_ecs.container_port
  discovery_service_arn     = module.backend_ecs.discovery_service_arn
  cognito_issuer            = local.cognito_issuer
  cognito_client_id         = module.cognito.client_id
  cors_allowed_origins      = local.browser_origins

  tags = local.common_tags
}

module "chat_agent" {
  source = "./agent_runtime"

  name_prefix          = local.name_prefix
  aws_region           = var.aws_region
  image_repository_url = module.ecr.repository_urls["agent"]
  image_repository_arn = module.ecr.repository_arns["agent"]
  image_tag            = var.agent_image_tag
  model_id             = var.chat_model_id
  api_base_url         = module.backend_api.api_url
  cognito_issuer       = local.cognito_issuer
  cognito_client_id    = module.cognito.client_id

  tags = local.common_tags
}

# Optional spend alert for the whole account (the first two budgets are free).
resource "aws_budgets_budget" "monthly" {
  count = var.budget_alert_email == "" ? 0 : 1

  name         = "${local.name_prefix}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  notification {
    comparison_operator        = "GREATER_THAN"
    threshold                  = 80
    threshold_type             = "PERCENTAGE"
    notification_type          = "ACTUAL"
    subscriber_email_addresses = [var.budget_alert_email]
  }
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
      cors_allowed_origins = local.browser_origins
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