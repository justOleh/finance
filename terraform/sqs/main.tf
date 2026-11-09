# Work queue + dead-letter queue. Messages that fail max_receive_count times land in the DLQ
# and stay there for 14 days so they can be inspected and redriven.
resource "aws_sqs_queue" "dlq" {
  name                      = "${var.name}-dlq"
  message_retention_seconds = 1209600 # 14 days, the maximum
  tags                      = var.tags
}

resource "aws_sqs_queue" "this" {
  name                       = var.name
  visibility_timeout_seconds = var.visibility_timeout_seconds
  receive_wait_time_seconds  = 20 # long polling by default
  tags                       = var.tags

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = var.max_receive_count
  })
}

# S3 is a different service, so it needs explicit permission to send to the queue. The two
# conditions stop other buckets (or other accounts) from using this queue.
data "aws_iam_policy_document" "s3_send" {
  statement {
    sid       = "AllowS3Notifications"
    actions   = ["sqs:SendMessage"]
    resources = [aws_sqs_queue.this.arn]

    principals {
      type        = "Service"
      identifiers = ["s3.amazonaws.com"]
    }

    condition {
      test     = "ArnEquals"
      variable = "aws:SourceArn"
      values   = [var.source_bucket_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
  }
}

resource "aws_sqs_queue_policy" "s3_send" {
  queue_url = aws_sqs_queue.this.id
  policy    = data.aws_iam_policy_document.s3_send.json
}
