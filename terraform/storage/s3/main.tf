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
  for_each = var.buckets

  # New buckets have Block Public Access enabled by default, so it must be
  # explicitly disabled (not just omitted) for buckets that serve public content.
  bucket                  = aws_s3_bucket.this[each.key].id
  block_public_acls       = each.value.block_public
  block_public_policy     = each.value.block_public
  ignore_public_acls      = each.value.block_public
  restrict_public_buckets = each.value.block_public
}

resource "aws_s3_bucket_cors_configuration" "this" {
  for_each = { for k, v in var.buckets : k => v if length(v.cors_allowed_origins) > 0 }

  bucket = aws_s3_bucket.this[each.key].id

  cors_rule {
    allowed_origins = each.value.cors_allowed_origins
    allowed_methods = each.value.cors_allowed_methods
    allowed_headers = ["*"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "this" {
  for_each = { for k, v in var.buckets : k => v if v.expiration_days != null }

  bucket = aws_s3_bucket.this[each.key].id

  rule {
    id     = "expire-objects"
    status = "Enabled"

    filter {}

    expiration {
      days = each.value.expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = each.value.expiration_days
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
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
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.this[each.key].arn}/*"
      }
    ]
  })
}