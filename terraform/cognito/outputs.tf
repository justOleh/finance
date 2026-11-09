output "user_pool_id" {
  description = "Cognito user pool id (backend validates tokens against it; frontend signs in to it)."
  value       = aws_cognito_user_pool.this.id
}

output "client_id" {
  description = "App client id of the web frontend (public, not a secret)."
  value       = aws_cognito_user_pool_client.web.id
}
