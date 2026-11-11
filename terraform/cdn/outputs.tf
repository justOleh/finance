output "url" {
  description = "HTTPS URL of the frontend."
  value       = "https://${aws_cloudfront_distribution.this.domain_name}"
}

output "distribution_id" {
  description = "Distribution id (needed to invalidate the cache after a deploy)."
  value       = aws_cloudfront_distribution.this.id
}
