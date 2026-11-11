# CloudFront in front of the frontend bucket (ADR-014): HTTPS for the site, and the bucket can be
# private. CloudFront reads the bucket through origin access control (OAC): requests are signed
# by CloudFront, and the bucket policy below accepts only this distribution.
# Cost: per request and per GB (the always-free tier covers a personal site); nothing while idle.
# Note: creating or deleting a distribution takes several minutes.

resource "aws_cloudfront_origin_access_control" "this" {
  name                              = "${var.name_prefix}-frontend"
  description                       = "CloudFront access to the private frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# AWS-managed cache policy: cache by path only, compress, long TTLs.
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_distribution" "this" {
  enabled             = true
  comment             = "${var.name_prefix} frontend"
  default_root_object = "index.html"
  price_class         = "PriceClass_100" # North America and Europe edges only: the cheapest class
  tags                = var.tags

  origin {
    origin_id                = "frontend"
    domain_name              = var.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.this.id
  }

  default_cache_behavior {
    target_origin_id       = "frontend"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # Single-page app: /dashboard, /chat ... are not objects in the bucket. A private bucket
  # answers 403 for a missing key, so both 403 and 404 return index.html and React Router
  # takes over.
  dynamic "custom_error_response" {
    for_each = [403, 404]
    content {
      error_code            = custom_error_response.value
      response_code         = 200
      response_page_path    = "/index.html"
      error_caching_min_ttl = 10
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # The free *.cloudfront.net certificate; a custom domain would need ACM in us-east-1.
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

data "aws_iam_policy_document" "bucket" {
  statement {
    sid       = "CloudFrontReadOnly"
    actions   = ["s3:GetObject"]
    resources = ["${var.bucket_arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    # Without this any CloudFront distribution (in any account) could read the bucket.
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.this.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "this" {
  bucket = var.bucket_id
  policy = data.aws_iam_policy_document.bucket.json
}
