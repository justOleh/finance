output "api_url" {
  description = "HTTPS base URL of the backend API (no trailing slash)."
  value       = aws_apigatewayv2_api.this.api_endpoint
}
