# Chat agent on Amazon Bedrock AgentCore Runtime (ADR-014).
#
#   Browser --Bearer <Cognito access token>--> AgentCore Runtime (verifies the token)
#     --> container (agent/, Strands) --> Bedrock (Claude)
#                                     --> the REST API, with the same token
#
# The agent has no data permissions at all: no DynamoDB, no S3. Its role can call one model and
# write its own logs; every expense it sees comes through the API with the caller's token.
# Cost: per use (CPU and memory while a session is active, plus Bedrock tokens); nothing idle.

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Runtime names allow letters, digits and underscores only.
  runtime_name = "${replace(var.name_prefix, "-", "_")}_chat"

  # "eu.amazon.nova-pro-v1:0" is an inference profile that routes to the model in several
  # EU regions. IAM needs both the profile and the underlying model in those regions.
  model_parts   = split(".", var.model_id)
  model_geo     = local.model_parts[0]
  base_model_id = join(".", slice(local.model_parts, 1, length(local.model_parts)))
  model_regions = local.model_geo == "eu" ? "eu-*" : "*"
}

# --- Role the agent code runs as ----------------------------------------------
data "aws_iam_policy_document" "assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }

    # Only AgentCore resources of this account may use the role (confused-deputy protection).
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:bedrock-agentcore:${var.aws_region}:${local.account_id}:*"]
    }
  }
}

resource "aws_iam_role" "this" {
  name               = "${var.name_prefix}-chat-agent"
  description        = "Assumed by the chat agent on AgentCore Runtime."
  assume_role_policy = data.aws_iam_policy_document.assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "this" {
  statement {
    sid     = "InvokeTheChatModelOnly"
    actions = ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"]
    resources = [
      "arn:aws:bedrock:${var.aws_region}:${local.account_id}:inference-profile/${var.model_id}",
      "arn:aws:bedrock:${local.model_regions}::foundation-model/${local.base_model_id}*",
    ]
  }

  statement {
    sid       = "PullOwnImage"
    actions   = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"]
    resources = [var.image_repository_arn]
  }

  statement {
    sid       = "EcrLogin"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # this action does not support resource-level permissions
  }

  statement {
    sid = "WriteOwnLogs"
    actions = [
      "logs:CreateLogGroup",
      "logs:CreateLogStream",
      "logs:PutLogEvents",
      "logs:DescribeLogStreams",
    ]
    resources = [
      "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*",
      "arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:/aws/bedrock-agentcore/runtimes/*:log-stream:*",
    ]
  }

  statement {
    sid       = "DescribeLogGroups"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["arn:aws:logs:${var.aws_region}:${local.account_id}:log-group:*"]
  }

  statement {
    sid = "Tracing"
    actions = [
      "xray:PutTraceSegments",
      "xray:PutTelemetryRecords",
      "xray:GetSamplingRules",
      "xray:GetSamplingTargets",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "Metrics"
    actions   = ["cloudwatch:PutMetricData"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "cloudwatch:namespace"
      values   = ["bedrock-agentcore"]
    }
  }
}

resource "aws_iam_role_policy" "this" {
  name   = "chat-agent"
  role   = aws_iam_role.this.id
  policy = data.aws_iam_policy_document.this.json
}

# --- The runtime ----------------------------------------------------------------
resource "aws_bedrockagentcore_agent_runtime" "this" {
  agent_runtime_name = local.runtime_name
  description        = "my-finance chat agent: a facade over the REST API (ADR-014)"
  role_arn           = aws_iam_role.this.arn
  tags               = var.tags

  agent_runtime_artifact {
    container_configuration {
      # A new tag creates a new runtime version; the DEFAULT endpoint follows the latest one.
      container_uri = "${var.image_repository_url}:${var.image_tag}"
    }
  }

  # PUBLIC = the container has outbound internet (Bedrock, the HTTP API), no VPC and no NAT.
  network_configuration {
    network_mode = "PUBLIC"
  }

  protocol_configuration {
    server_protocol = "HTTP"
  }

  # Inbound auth: AgentCore verifies the Cognito access token (signature, issuer, expiry and
  # client id) before the container sees the request. Without this block the runtime would
  # expect IAM-signed (SigV4) calls, which a browser cannot make.
  authorizer_configuration {
    custom_jwt_authorizer {
      discovery_url   = "${var.cognito_issuer}/.well-known/openid-configuration"
      allowed_clients = [var.cognito_client_id]
    }
  }

  # Headers are dropped unless listed. The agent needs the caller's token to call the API on
  # their behalf (identity propagation, ADR-014 decision 4).
  request_header_configuration {
    request_header_allowlist = ["Authorization"]
  }

  environment_variables = {
    API_BASE_URL          = var.api_base_url
    MODEL_ID              = var.model_id
    AWS_REGION            = var.aws_region
    MAX_TOOL_CALLS        = tostring(var.max_tool_calls)
    MAX_OUTPUT_TOKENS     = tostring(var.max_output_tokens)
    MAX_TURNS_PER_SESSION = tostring(var.max_turns_per_session)
  }

  depends_on = [aws_iam_role_policy.this]
}
