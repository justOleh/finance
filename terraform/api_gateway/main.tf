# HTTPS front door for the backend (ADR-014): API Gateway HTTP API -> VPC link -> Cloud Map ->
# Fargate task. It gives the API what the bare task IP could not (ADR-007, ADR-011):
#  - TLS and a stable URL, with no load balancer
#  - the Cognito token checked before a request reaches the task (the backend checks it again)
#  - throttling
# Cost: per request ($1 per million), nothing while idle. A VPC link for HTTP APIs has no
# hourly charge at the time of writing; confirm on the API Gateway pricing page.

# --- VPC link: API Gateway's network interfaces inside the VPC ------------------
resource "aws_security_group" "vpc_link" {
  name        = "${var.name_prefix}-api-vpc-link"
  description = "API Gateway VPC link: may only call the backend port"
  vpc_id      = var.vpc_id
  tags        = var.tags
}

resource "aws_vpc_security_group_egress_rule" "to_backend" {
  security_group_id            = aws_security_group.vpc_link.id
  description                  = "To the backend task"
  ip_protocol                  = "tcp"
  from_port                    = var.backend_port
  to_port                      = var.backend_port
  referenced_security_group_id = var.backend_security_group_id
}

# The backend accepts traffic from the VPC link and from nowhere else.
resource "aws_vpc_security_group_ingress_rule" "backend_from_vpc_link" {
  security_group_id            = var.backend_security_group_id
  description                  = "Backend API, only from the API Gateway VPC link"
  ip_protocol                  = "tcp"
  from_port                    = var.backend_port
  to_port                      = var.backend_port
  referenced_security_group_id = aws_security_group.vpc_link.id
}

resource "aws_apigatewayv2_vpc_link" "this" {
  name               = "${var.name_prefix}-backend"
  subnet_ids         = var.subnet_ids
  security_group_ids = [aws_security_group.vpc_link.id]
  tags               = var.tags
}

# --- API ----------------------------------------------------------------------
resource "aws_apigatewayv2_api" "this" {
  name          = "${var.name_prefix}-api"
  description   = "Public HTTPS entry to the my-finance backend"
  protocol_type = "HTTP"
  tags          = var.tags

  # With CORS configured here, API Gateway adds the CORS headers itself and ignores those sent
  # by the backend. It does NOT exempt preflight requests from the authorizer: see the OPTIONS
  # route below.
  cors_configuration {
    allow_origins = var.cors_allowed_origins
    allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "idempotency-key"]
    max_age       = 3600
  }
}

# Cognito access tokens carry `client_id` instead of `aud`; the JWT authorizer accepts either
# and compares it with `audience`.
resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.this.id
  name             = "cognito"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    issuer   = var.cognito_issuer
    audience = [var.cognito_client_id]
  }
}

resource "aws_apigatewayv2_integration" "backend" {
  api_id             = aws_apigatewayv2_api.this.id
  integration_type   = "HTTP_PROXY"
  integration_method = "ANY"
  connection_type    = "VPC_LINK"
  connection_id      = aws_apigatewayv2_vpc_link.this.id
  # A Cloud Map service ARN: API Gateway looks up the healthy task (IP and port) per request.
  integration_uri        = var.discovery_service_arn
  payload_format_version = "1.0"
}

# Everything needs a valid token...
resource "aws_apigatewayv2_route" "default" {
  api_id             = aws_apigatewayv2_api.this.id
  route_key          = "$default"
  target             = "integrations/${aws_apigatewayv2_integration.backend.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

# ...except CORS preflight. Browsers send OPTIONS without the Authorization header, and the
# `$default` route catches every method, so without this route the authorizer answers the
# preflight with 401 and the browser blocks the real request. A more specific route wins over
# `$default`, and this one has no authorizer. A preflight carries no data and changes nothing.
resource "aws_apigatewayv2_route" "preflight" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "OPTIONS /{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.backend.id}"
}

# ...and the health check. (/docs and / are no longer reachable without a token.)
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.this.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.backend.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.this.id
  name        = "$default"
  auto_deploy = true
  tags        = var.tags

  default_route_settings {
    throttling_rate_limit  = var.throttling_rate_limit
    throttling_burst_limit = var.throttling_burst_limit
  }
}
