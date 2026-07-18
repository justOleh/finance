#!/usr/bin/env bash
# Deploy my-finance.
#
# Local (docker compose):
#   ./deploy.sh --env local              # build + start all containers
#   ./deploy.sh --env local --down       # stop and remove containers
#   ./deploy.sh --env local --logs       # follow container logs
#
# AWS (not implemented yet):
#   Frontend  -> npm build + terragrunt apply (uploads dist/ as aws_s3_object)
#   Backend   -> docker build + push to ECR + ECS force-new-deployment
#   Parser    -> docker build + push to ECR + ECS force-new-deployment
#
# Env overrides (all optional):
#   PROJECT=my-finance ENV_NAME=prod AWS_REGION=us-east-1 IMAGE_TAG=$(git rev-parse --short HEAD)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yml"
ENVS_DIR="${SCRIPT_DIR}/envs"

ENV_NAME=""
ACTION="up"

usage() {
    cat <<EOF
Usage: $(basename "$0") --env <local|prod> [options]

Options:
  --env <name>   Target environment (currently supported: local)
  --down         (local only) Stop and remove containers
  --logs         (local only) Follow container logs
  -h, --help     Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            ENV_NAME="${2:-}"
            shift 2
            ;;
        --down)
            ACTION="down"
            shift
            ;;
        --logs)
            ACTION="logs"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ -z "$ENV_NAME" ]]; then
    echo "Error: --env is required" >&2
    usage
    exit 1
fi

# Resolve `docker compose` (v2) vs legacy `docker-compose` (v1).
if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo "Error: neither 'docker compose' nor 'docker-compose' is available" >&2
    exit 1
fi

deploy_local() {
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        echo "Error: compose file not found at $COMPOSE_FILE" >&2
        exit 1
    fi

    local env_file="${ENVS_DIR}/local.env"
    if [[ ! -f "$env_file" ]]; then
        echo "Error: env file not found at $env_file" >&2
        exit 1
    fi

    # --env-file makes ${VAR} in docker-compose.yml resolve against local.env.
    # (Per-service `env_file:` blocks in the compose file additionally inject
    #  the same vars into each container's runtime environment.)
    local -a compose_cmd=("${COMPOSE[@]}" --env-file "$env_file" -f "$COMPOSE_FILE")

    # Also load the vars into this shell so the echo below can use them.
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a

    # Required vars — fail loudly if the env file is missing any of these
    # rather than silently falling back to hardcoded ports.
    local var
    for var in BACKEND_PORT RECEIPT_PARSER_PORT FRONTEND_PORT; do
        if [[ -z "${!var:-}" ]]; then
            echo "Error: $var is not set in $env_file" >&2
            exit 1
        fi
    done

    case "$ACTION" in
        up)
            echo ">> Building and starting local containers via docker compose..."
            "${compose_cmd[@]}" up --build -d
            echo ">> Services:"
            "${compose_cmd[@]}" ps
            cat <<EOF

Local stack is up:
  frontend        http://localhost:${FRONTEND_PORT}
  backend API     http://localhost:${BACKEND_PORT}
  receipt parser  http://localhost:${RECEIPT_PARSER_PORT}

Tail logs:  ./$(basename "$0") --env local --logs
Stop:       ./$(basename "$0") --env local --down
EOF
            ;;
        down)
            echo ">> Stopping local containers..."
            "${compose_cmd[@]}" down
            ;;
        logs)
            "${compose_cmd[@]}" logs -f
            ;;
    esac
}

case "$ENV_NAME" in
    local)
        deploy_local
        ;;
    prod|aws)
        echo "Error: '$ENV_NAME' deployment is not implemented yet." >&2
        exit 2
        ;;
    *)
        echo "Error: unknown env '$ENV_NAME' (expected: local)" >&2
        exit 1
        ;;
esac
