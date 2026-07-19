resource "aws_s3_bucket" "this" {
  for_each = var.buckets

  bucket        = each.value.name
  force_destroy = each.value.force_destroy
  tags          = var.tags
}

resource "aws_s3_bucket_versioning" "this" {
  for_each = { for k, v in var.buckets : k => v if v.versioning }

  bucket = aws_s3_bucket.this[each.key].id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "this" {
  for_each = var.buckets

  bucket = aws_s3_bucket.this[each.key].id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = each.value.sse_algorithm
    }
  }
}

resource "aws_s3_bucket_public_access_block" "this" {
  for_each = { for k, v in var.buckets : k => v if v.block_public }

  bucket                  = aws_s3_bucket.this[each.key].id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_website_configuration" "this" {
  for_each = { for k, v in var.buckets : k => v if v.website_hosting }

  bucket = aws_s3_bucket.this[each.key].id

  index_document {
    suffix = each.value.index_document
  }

  error_document {
    key = each.value.error_document
  }
}

resource "aws_s3_bucket_policy" "public_read" {
  for_each = { for k, v in var.buckets : k => v if v.website_hosting }

  bucket = aws_s3_bucket.this[each.key].id

  # Ensure public access block is removed before applying policy
  depends_on = [aws_s3_bucket_public_access_block.this]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "PublicReadGetObject"
        Effect = "Allow"
        Principal = "*"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.this[each.key].arn}/*"
      }
    ]
  })
}
