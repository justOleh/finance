# User pool = the user directory + token issuer. Personal app: nobody can sign
# themselves up, users are created by the admin (console or CLI, see terraform/README.md).
resource "aws_cognito_user_pool" "this" {
  name = "${var.name_prefix}-users"

  # Email is the login name.
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = false
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  tags = var.tags
}

# App client = the browser SPA. A browser cannot keep a secret, so no client secret;
# SRP means the password is never sent to Cognito, only a proof of it.
resource "aws_cognito_user_pool_client" "web" {
  name         = "${var.name_prefix}-web"
  user_pool_id = aws_cognito_user_pool.this.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]

  access_token_validity  = var.access_token_minutes
  id_token_validity      = var.access_token_minutes
  refresh_token_validity = var.refresh_token_days

  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }

  # Same error for "no such user" and "wrong password" (no account enumeration).
  prevent_user_existence_errors = "ENABLED"
}
