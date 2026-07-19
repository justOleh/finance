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

deploy_aws_frontend() {
    local frontend_dir="${SCRIPT_DIR}/frontend"
    
    if [[ ! -d "$frontend_dir" ]]; then
        echo "Error: frontend directory not found at $frontend_dir" >&2
        exit 1
    fi

    echo ">> Building frontend..."
    cd "$frontend_dir"
    
    if [[ ! -f "package.json" ]]; then
        echo "Error: package.json not found in $frontend_dir" >&2
        exit 1
    fi

    npm install
    npm run build
    
    if [[ ! -d "dist" ]]; then
        echo "Error: dist directory not created after build" >&2
        exit 1
    fi
    
    echo "✓ Frontend build successful"
    
    echo ">> Getting S3 bucket name from terraform outputs..."
    local terraform_dir="${SCRIPT_DIR}/terraform"
    cd "$terraform_dir"
    
    local bucket_id
    bucket_id=$(terraform output -raw 'frontend_bucket_id' 2>/dev/null || echo "")
    
    if [[ -z "$bucket_id" ]]; then
        echo "Error: could not get frontend bucket name from terraform" >&2
        exit 1
    fi
    
    echo ">> Uploading frontend to S3 bucket: $bucket_id"
    
    # Upload dist files to S3 (bucket policy allows public read)
    aws s3 sync "$frontend_dir/dist" "s3://$bucket_id/" \
        --delete \
        --cache-control "public, max-age=3600" \
        --exclude ".git/*"
    
    echo "✓ Frontend deployed to S3"
    cd - > /dev/null
}

deploy_aws_infra() {
    local terraform_dir="${SCRIPT_DIR}/terraform"
    
    if [[ ! -d "$terraform_dir" ]]; then
        echo "Error: terraform directory not found at $terraform_dir" >&2
        exit 1
    fi

    echo ">> Initializing terraform..."
    cd "$terraform_dir"
    
    if ! terraform init; then
        echo "Error: terraform init failed" >&2
        exit 1
    fi

    echo ">> Checking AWS infrastructure with terraform plan..."
    
    # Run terraform plan and capture output
    if ! terraform plan -out=tfplan; then
        echo "Error: terraform plan failed" >&2
        exit 1
    fi
    
    # Check if there are any changes
    if terraform show tfplan | grep -q "No changes"; then
        echo "✓ AWS infrastructure is up to date. No changes needed."
    else
        echo ""
        echo "⚠️  AWS infrastructure changes detected:"
        terraform show tfplan
        echo ""
        echo "To proceed with these infrastructure changes, type: CHANGE_INFRA"
        read -p "Confirm: " -r confirmation
        
        if [[ "$confirmation" != "CHANGE_INFRA" ]]; then
            echo "Deployment cancelled."
            rm -f tfplan
            exit 0
        fi
        
        echo ">> Applying terraform changes..."
        terraform apply tfplan
        rm -f tfplan
        echo "✓ AWS infrastructure updated successfully."
    fi
    
    cd - > /dev/null
}

deploy_aws() {
    echo "=========================================="
    echo "  AWS Deployment - Frontend & Infrastructure"
    echo "=========================================="
    echo ""
    
    # Stage 1: Infrastructure
    echo "[Stage 1/2] Infrastructure"
    deploy_aws_infra
    echo ""
    
    # Stage 2: Frontend
    echo "[Stage 2/2] Frontend"
    deploy_aws_frontend
    echo ""
    
    echo "=========================================="
    echo "✓ AWS deployment completed successfully!"
    echo "=========================================="
}

case "$ENV_NAME" in
    local)
        deploy_local
        ;;
    prod|aws)
        deploy_aws
        ;;
    *)
        echo "Error: unknown env '$ENV_NAME' (expected: local or aws)" >&2
        exit 1
        ;;
esac
