# Trust policy: WHO may assume the role.
# For now only your own IAM user/role (running the backend locally, via an AWS
# CLI profile with role_arn). When the backend moves to AWS, add a second
# statement with a Service principal (e.g. ecs-tasks.amazonaws.com).
data "aws_iam_policy_document" "backend_assume" {
  statement {
    sid     = "LocalDevAssumeRole"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = var.local_dev_principal_arns
    }
  }

  # ECS tasks assume this role automatically; boto3 picks the credentials up.
  statement {
    sid     = "EcsTaskAssumeRole"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backend" {
  name               = "${var.name_prefix}-backend"
  description        = "Assumed locally by the my-finance backend to access its DynamoDB table."
  assume_role_policy = data.aws_iam_policy_document.backend_assume.json
  tags               = var.tags
}

# Permissions policy: WHAT the role may do, scoped to specific table ARNs.
data "aws_iam_policy_document" "backend_dynamodb" {
  statement {
    sid = "AppTableReadWrite"
    actions = [
      "dynamodb:PutItem",
      "dynamodb:GetItem",
      "dynamodb:UpdateItem",
      "dynamodb:DeleteItem",
      "dynamodb:Query",
      "dynamodb:BatchWriteItem",
    ]
    # Querying a GSI is authorized against the index ARN, not the table ARN.
    resources = concat(
      var.dynamodb_table_arns,
      [for arn in var.dynamodb_table_arns : "${arn}/index/*"],
    )
  }
}

resource "aws_iam_role_policy" "backend_dynamodb" {
  name   = "dynamodb-access"
  role   = aws_iam_role.backend.id
  policy = data.aws_iam_policy_document.backend_dynamodb.json
}

# A presigned POST is only valid if the signer itself may perform the upload, so the backend
# needs s3:PutObject. It cannot read or list receipts, and the worker has its own role.
data "aws_iam_policy_document" "backend_receipts_upload" {
  statement {
    sid       = "ReceiptsUploadOnly"
    actions   = ["s3:PutObject"]
    resources = ["${var.receipts_bucket_arn}/receipts/*"]
  }
}

resource "aws_iam_role_policy" "backend_receipts_upload" {
  name   = "receipts-upload"
  role   = aws_iam_role.backend.id
  policy = data.aws_iam_policy_document.backend_receipts_upload.json
}
