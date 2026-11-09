# Lambda "parse receipt" (ADR-013): SQS -> Claude (Anthropic API) -> DynamoDB.
# The queue is filled by the converted bucket's ObjectCreated notification.
#
# Unlike the old Fargate worker (ADR-010) it runs only while there are messages, and it needs
# no VPC, public IP or NAT gateway: a Lambda outside a VPC can reach the internet.

resource "aws_cloudwatch_log_group" "this" {
  name              = "/aws/lambda/${var.name_prefix}-parse-receipt"
  retention_in_days = var.log_retention_days
  tags              = var.tags
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

# Separate from the backend role on purpose: this function can read converted receipts and
# update receipt records, the backend can sign uploads but not read them.
resource "aws_iam_role" "this" {
  name               = "${var.name_prefix}-parse-receipt"
  description        = "Assumed by the parse-receipt Lambda."
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "this" {
  # What the SQS event source mapping needs to poll and delete messages on our behalf.
  statement {
    sid = "ConsumeQueue"
    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes",
    ]
    resources = [var.queue_arn]
  }

  statement {
    sid       = "ReadConvertedImages"
    actions   = ["s3:GetObject"]
    resources = ["${var.converted_bucket_arn}/receipts/*"]
  }

  # Updates the receipt record only (it never creates items or reads other data). The expense
  # is created by the backend when the user saves the reviewed draft.
  statement {
    sid       = "UpdateReceiptRecords"
    actions   = ["dynamodb:UpdateItem"]
    resources = var.dynamodb_table_arns
  }

  statement {
    sid       = "WriteLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.this.arn}:*"]
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "parse-receipt-access"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

# --- Function -----------------------------------------------------------------
resource "aws_lambda_function" "this" {
  function_name = "${var.name_prefix}-parse-receipt"
  role          = aws_iam_role.this.arn
  package_type  = "Image"
  image_uri     = "${var.image_repository_url}:${var.image_tag}"
  architectures = ["arm64"]
  memory_size   = var.memory_size
  timeout       = var.timeout_seconds
  tags          = var.tags

  environment {
    variables = merge(var.environment, {
      # Placeholder only. Set the real key in the Lambda console (Configuration > Environment
      # variables); ignore_changes below stops Terraform from overwriting it.
      ANTHROPIC_API_KEY = var.anthropic_api_key_placeholder
    })
  }

  lifecycle {
    ignore_changes = [environment[0].variables["ANTHROPIC_API_KEY"]]
  }

  depends_on = [aws_cloudwatch_log_group.this, aws_iam_role_policy.this]
}

resource "aws_lambda_event_source_mapping" "queue" {
  event_source_arn = var.queue_arn
  function_name    = aws_lambda_function.this.arn

  # One receipt per invocation: simple retries, and a failure affects only that receipt.
  batch_size = 1
  # Lets the handler report which messages failed (batchItemFailures) instead of failing all.
  function_response_types = ["ReportBatchItemFailures"]

  # Caps parallel model calls: spend control and fewer 429s from the API (minimum is 2).
  scaling_config {
    maximum_concurrency = var.maximum_concurrency
  }
}
