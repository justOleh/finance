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
  --env <name>   Target environment (local, aws|prod)
  --down         local: stop and remove containers; aws: terraform destroy
  --logs         (local only) Follow container logs
  --destroy      (aws only) Destroy AWS resources
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
        --destroy)
            ACTION="destroy"
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

# # Resolve `docker compose` (v2) vs legacy `docker-compose` (v1).
# if docker compose version >/dev/null 2>&1; then
#     COMPOSE=(docker compose)
# elif command -v docker-compose >/dev/null 2>&1; then
#     COMPOSE=(docker-compose)
# else
#     echo "Error: neither 'docker compose' nor 'docker-compose' is available" >&2
#     exit 1
# fi

# deploy_local() {
#     if [[ ! -f "$COMPOSE_FILE" ]]; then
#         echo "Error: compose file not found at $COMPOSE_FILE" >&2
#         exit 1
#     fi

#     local env_file="${ENVS_DIR}/local.env"
#     if [[ ! -f "$env_file" ]]; then
#         echo "Error: env file not found at $env_file" >&2
#         exit 1
#     fi

#     # --env-file makes ${VAR} in docker-compose.yml resolve against local.env.
#     # (Per-service `env_file:` blocks in the compose file additionally inject
#     #  the same vars into each container's runtime environment.)
#     local -a compose_cmd=("${COMPOSE[@]}" --env-file "$env_file" -f "$COMPOSE_FILE")

#     # Also load the vars into this shell so the echo below can use them.
#     set -a
#     # shellcheck disable=SC1090
#     source "$env_file"
#     set +a

#     # Required vars — fail loudly if the env file is missing any of these
#     # rather than silently falling back to hardcoded ports.
#     local var
#     for var in BACKEND_PORT RECEIPT_PARSER_PORT FRONTEND_PORT; do
#         if [[ -z "${!var:-}" ]]; then
#             echo "Error: $var is not set in $env_file" >&2
#             exit 1
#         fi
#     done

#     case "$ACTION" in
#         up)
#             echo ">> Building and starting local containers via docker compose..."
#             "${compose_cmd[@]}" up --build -d
#             echo ">> Services:"
#             "${compose_cmd[@]}" ps
#             cat <<EOF

# Local stack is up:
#   frontend        http://localhost:${FRONTEND_PORT}
#   backend API     http://localhost:${BACKEND_PORT}
#   receipt parser  http://localhost:${RECEIPT_PARSER_PORT}

# Tail logs:  ./$(basename "$0") --env local --logs
# Stop:       ./$(basename "$0") --env local --down
# EOF
#             ;;
#         down)
#             echo ">> Stopping local containers..."
#             "${compose_cmd[@]}" down
#             ;;
#         logs)
#             "${compose_cmd[@]}" logs -f
#             ;;
#     esac
# }

deploy_aws() {
    deploy_frontend() {
        echo ">> Deploying frontend to AWS S3..."
        echo ">> Creating S3 bucket (if not exists)..."
        cd "${SCRIPT_DIR}/terraform"
        terraform init
        terraform apply -target=module.frontend_bucket -var force_destroy_buckets=true -auto-approve

        echo ">> Building frontend..."
        cd "${SCRIPT_DIR}/frontend"
        npm install
        npm run build

        echo ">> Uploading frontend build to S3..."
        local bucket
        bucket="$(terraform -chdir="${SCRIPT_DIR}/terraform" output -raw frontend_bucket)"
        aws s3 sync "${SCRIPT_DIR}/frontend/dist" "s3://${bucket}" --delete
    }

    deploy_backend() {
        echo ">> Deploying backend to AWS ECS..."
        echo ">> Not implemented yet."
    }

    deploy_parser() {
        echo ">> Deploying receipt parser to AWS ECS..."
        echo ">> Not implemented yet."
    }

    deploy_storage() {
        echo ">> Deploying storage to AWS..."
        echo ">> Creating DynamoDB table (if not exists)..."
        
        cd "${SCRIPT_DIR}/terraform"
        terraform init
        terraform apply -target=module.dynamodb_table -var force_destroy_buckets=true -auto-approve
    }

    deploy_frontend
    deploy_storage
    # deploy_backend
    # deploy_parser
}

destroy_aws() {
    echo ">> Destroying AWS resources..."
    cd "${SCRIPT_DIR}/terraform"
    terraform init
    terraform destroy -target=module.frontend_bucket -auto-approve
}

case "$ENV_NAME" in
    local)
        deploy_local
        ;;
    prod|aws)
        case "$ACTION" in
            up)   deploy_aws ;;
            down) destroy_aws ;;
            logs)
                echo "Error: --logs is not supported for aws" >&2
                exit 1
                ;;
        esac
        ;;
    *)
        echo "Error: unknown env '$ENV_NAME' (expected: local|aws|prod)" >&2
        exit 1
        ;;
esac
