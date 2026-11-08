output "backend_role_arn" {
  description = "ARN of the backend role (use as role_arn in an AWS CLI profile)."
  value       = aws_iam_role.backend.arn
}

output "backend_role_name" {
  description = "Name of the backend task role."
  value       = aws_iam_role.backend.name
}