# Lambda "convert image" (ADR-013): any image format in the uploads bucket -> PNG in the
# converted bucket. Triggered directly by S3 (asynchronous invocation).
#
# Asynchronous invocation retries twice and then drops the event, so a failure destination (an
# SQS queue) keeps the events of files that could not be converted, for inspection.

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name_prefix}-convert-image"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

# Failed conversions (after the automatic retries) end up here for 14 days.
resource "aws_sqs_queue" "failures" {
  name                      = "${var.name_prefix}-convert-failures"
  message_retention_seconds = 1209600
  tags                      = var.tags
}

# --- Role ---------------------------------------------------------------------
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name_prefix}-convert-image"
  description        = "Assumed by the convert-image Lambda."
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "this" {
  statement {
    sid       = "ReadUploads"
    actions   = ["s3:GetObject"]
    resources = ["${var.uploads_bucket_arn}/receipts/*"]
  }

  statement {
    sid       = "WriteConverted"
    actions   = ["s3:PutObject"]
    resources = ["${var.converted_bucket_arn}/receipts/*"]
  }

  statement {
    sid       = "ReportFailures"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.failures.arn]
  }

  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "convert-image-access"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

# --- Function -----------------------------------------------------------------
resource "aws_lambda_function" "this" {
  function_name = "${var.name_prefix}-convert-image"
  role          = aws_iam_role.this.arn
  package_type  = "Image"
  image_uri     = "${var.image_repository_url}:${var.image_tag}"
  architectures = ["arm64"] # matches the arm64 image built on Apple Silicon
  memory_size   = var.memory_size
  timeout       = var.timeout_seconds
  tags          = var.tags

  environment {
    variables = {
      DEST_BUCKET    = var.converted_bucket_name
      MAX_IMAGE_EDGE = tostring(var.max_image_edge)
    }
  }

  # The log group (retention) must exist before the function logs to it.
  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy.this]
}

resource "aws_lambda_function_event_invoke_config" "this" {
  function_name                = aws_lambda_function.this.function_name
  maximum_retry_attempts       = 2
  maximum_event_age_in_seconds = 3600

  destination_config {
    on_failure {
      destination = aws_sqs_queue.failures.arn
    }
  }
}

# S3 is a different service, so it needs explicit permission to invoke the function. The two
# conditions stop other buckets (or other accounts) from using it.
resource "aws_lambda_permission" "s3" {
  statement_id   = "AllowInvokeFromUploadsBucket"
  action         = "lambda:InvokeFunction"
  function_name  = aws_lambda_function.this.function_name
  principal      = "s3.amazonaws.com"
  source_arn     = var.uploads_bucket_arn
  source_account = var.account_id
}
