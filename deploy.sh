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

    case "$ACTION" in
        up)
            echo ">> Building and starting local containers via docker compose..."
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" up --build -d
            echo ">> Services:"
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" ps
            cat <<EOF

Local stack is up:
  frontend        http://localhost:8501
  backend API     http://localhost:8000
  receipt parser  http://localhost:8001

Tail logs:  ./$(basename "$0") --env local --logs
Stop:       ./$(basename "$0") --env local --down
EOF
            ;;
        down)
            echo ">> Stopping local containers..."
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" down
            ;;
        logs)
            "${COMPOSE[@]}" -f "$COMPOSE_FILE" logs -f
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
