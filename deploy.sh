#!/usr/bin/env bash
# Deploy my-finance.
#
# Local (docker compose):
#   ./deploy.sh --env local              # build + start all containers
#   ./deploy.sh --env local --down       # stop and remove containers
#   ./deploy.sh --env local --logs       # follow container logs
#
# AWS (no ALB, no NAT: Fargate task behind an API Gateway HTTP API, frontend behind CloudFront):
#   Registry  -> terraform apply -target=module.ecr (ECR outlives --down)
#   Images    -> docker build + push: backend, the two Lambdas, the chat agent
#   Infra     -> terraform apply (S3, CloudFront, SQS, DynamoDB, IAM, ECS, HTTP API, Lambda,
#                AgentCore Runtime). The agent image tag is passed in, so a new build becomes a
#                new runtime version.
#   Backend   -> ECS force-new-deployment
#   Lambdas   -> lambda update-function-code
#                (convert-image: any format -> PNG, parse-receipt: SQS -> Claude -> DynamoDB)
#   Frontend  -> npm build with the API URL and the agent URL + s3 sync + CloudFront invalidation
#
# The parse-receipt Lambda needs ANTHROPIC_API_KEY: set it once in the Lambda console
# (Configuration > Environment variables). Terraform only creates a placeholder and never
# overwrites the value afterwards.
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
Usage: $(basename "$0") --env <local|aws|prod> [options]

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

deploy_aws() {
    local region="${AWS_REGION:-eu-west-1}"
    local tf_dir="${SCRIPT_DIR}/terraform"
    export AWS_REGION="$region" AWS_DEFAULT_REGION="$region"

    tf_output() { terraform -chdir="$tf_dir" output -raw "$1"; }

    # One tag per agent build: the commit, plus a timestamp when agent/ has uncommitted changes.
    # AgentCore Runtime only starts a new version when the image reference changes, so a fixed
    # ":latest" (as used for the backend and the Lambdas) would never roll out new code.
    local agent_tag
    agent_tag="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD)"
    if [[ -n "$(git -C "$SCRIPT_DIR" status --porcelain -- agent)" ]]; then
        agent_tag="${agent_tag}-$(date +%Y%m%d%H%M%S)"
    fi

    # 1. Registry first, so the image exists before the ECS service is created.
    deploy_registry() {
        echo ">> Creating ECR repositories..."
        terraform -chdir="$tf_dir" init
        terraform -chdir="$tf_dir" apply -auto-approve -target=module.ecr
    }

    # 2. Build + push the backend image.
    push_backend_image() {
        echo ">> Building and pushing backend image..."
        local repo registry
        repo="$(tf_output backend_ecr_repository_url)"
        registry="${repo%%/*}"

        aws ecr get-login-password --region "$region" \
            | docker login --username AWS --password-stdin "$registry"

        # Fargate task runs on ARM64 (see terraform/ecs), same as Apple Silicon.
        docker build --platform linux/arm64 -t "${repo}:latest" "${SCRIPT_DIR}/backend"
        docker push "${repo}:latest"
    }

    # 2b. Build + push the Lambda images (must exist before the functions are created).
    #     --provenance=false: Lambda rejects the attestation manifests buildx adds by default.
    push_lambda_image() {
        local output_name="$1" dir="$2" repo registry
        echo ">> Building and pushing ${dir} Lambda image..."
        repo="$(tf_output "$output_name")"
        registry="${repo%%/*}"

        aws ecr get-login-password --region "$region" \
            | docker login --username AWS --password-stdin "$registry"

        docker build --platform linux/arm64 --provenance=false \
            -t "${repo}:latest" "${SCRIPT_DIR}/lambdas/${dir}"
        docker push "${repo}:latest"
    }

    push_lambda_images() {
        push_lambda_image convert_image_ecr_repository_url convert_image
        push_lambda_image parse_receipt_ecr_repository_url parse_receipt
    }

    # 2c. Build + push the chat agent image (must exist before the runtime is created).
    #      AgentCore Runtime runs arm64 containers only.
    push_agent_image() {
        local repo registry
        echo ">> Building and pushing the chat agent image (tag ${agent_tag})..."
        repo="$(tf_output agent_ecr_repository_url)"
        registry="${repo%%/*}"

        aws ecr get-login-password --region "$region" \
            | docker login --username AWS --password-stdin "$registry"

        docker build --platform linux/arm64 --provenance=false \
            -t "${repo}:${agent_tag}" "${SCRIPT_DIR}/agent"
        docker push "${repo}:${agent_tag}"
    }

    # 3. Everything else (buckets, CloudFront, queue, DynamoDB, IAM, ECS, HTTP API, Lambda,
    #    AgentCore Runtime). The first run creates a CloudFront distribution: allow 5-15 minutes.
    deploy_infra() {
        echo ">> Applying Terraform (buckets, CloudFront, SQS, DynamoDB, IAM, ECS, HTTP API, Lambda, agent)..."
        terraform -chdir="$tf_dir" apply -auto-approve \
            -var force_destroy_buckets=true \
            -var "agent_image_tag=${agent_tag}"
    }

    # 4. Roll the service onto the freshly pushed image (the task definition
    #    always says ":latest", so Terraform alone sees no change on redeploys).
    deploy_backend() {
        echo ">> Deploying backend to AWS ECS..."
        local cluster service
        cluster="$(tf_output ecs_cluster_name)"
        service="$(tf_output ecs_backend_service_name)"
        aws ecs update-service --cluster "$cluster" --service "$service" \
            --force-new-deployment >/dev/null
        echo ">> Waiting for the service to become stable..."
        aws ecs wait services-stable --cluster "$cluster" --services "$service"
    }

    # The frontend talks to two HTTPS endpoints, both stable across backend restarts:
    # the API Gateway URL (REST API) and the AgentCore Runtime URL (chat).
    deploy_frontend() {
        local api_url agent_url bucket pool_id client_id distribution
        api_url="$(tf_output api_url)"
        agent_url="$(tf_output agent_invoke_url)"
        pool_id="$(tf_output cognito_user_pool_id)"
        client_id="$(tf_output cognito_client_id)"
        echo ">> Building frontend against API ${api_url}..."
        (
            cd "${SCRIPT_DIR}/frontend"
            npm install
            VITE_BACKEND_URL="$api_url" \
                VITE_AGENT_URL="$agent_url" \
                VITE_COGNITO_USER_POOL_ID="$pool_id" \
                VITE_COGNITO_CLIENT_ID="$client_id" \
                npm run build
        )

        echo ">> Uploading frontend build to S3..."
        bucket="$(tf_output frontend_bucket)"
        aws s3 sync "${SCRIPT_DIR}/frontend/dist" "s3://${bucket}" --delete

        # CloudFront caches index.html; without this the old bundle is served for up to a day.
        # (The first 1,000 invalidation paths per month are free.)
        distribution="$(tf_output frontend_distribution_id)"
        aws cloudfront create-invalidation --distribution-id "$distribution" --paths '/*' >/dev/null

        echo ">> Frontend: $(tf_output frontend_hosting_url)"
        echo ">> API:      ${api_url}/health"
        echo ">> Chat:     AgentCore runtime $(tf_output agent_runtime_id) (image tag ${agent_tag})"
    }

    # Same ":latest" trick as the backend: Lambda resolves the tag to an image digest when the
    # code is updated, so pushing :latest alone changes nothing. Point each function at the
    # freshly pushed image and wait until the update is finished.
    deploy_lambdas() {
        local output_name function repo
        for output_name in convert_image_function_name parse_receipt_function_name; do
            function="$(tf_output "$output_name")"
            case "$output_name" in
                convert_image_*) repo="$(tf_output convert_image_ecr_repository_url)" ;;
                *)               repo="$(tf_output parse_receipt_ecr_repository_url)" ;;
            esac
            echo ">> Updating Lambda ${function}..."
            aws lambda update-function-code --function-name "$function" \
                --image-uri "${repo}:latest" --architectures arm64 >/dev/null
            aws lambda wait function-updated --function-name "$function"
        done
        warn_if_api_key_missing
    }

    # The key itself is never printed: only compared with the Terraform placeholder.
    warn_if_api_key_missing() {
        local function key
        function="$(tf_output parse_receipt_function_name)"
        key="$(aws lambda get-function-configuration --function-name "$function" \
            --query 'Environment.Variables.ANTHROPIC_API_KEY' --output text)"
        if [[ -z "$key" || "$key" == "None" || "$key" == "set-me-in-the-lambda-console" ]]; then
            echo ">> WARNING: ANTHROPIC_API_KEY is not set on Lambda ${function}." >&2
            echo ">>          Set it in the AWS console (Lambda > Configuration > Environment variables);" >&2
            echo ">>          until then every parse fails and ends in the dead-letter queue." >&2
        fi
    }

    # Order matters: images must exist before Terraform creates the things that run them, and
    # the frontend bundle needs the API and agent URLs that Terraform outputs.
    deploy_registry
    push_backend_image
    push_lambda_images
    push_agent_image
    deploy_infra
    deploy_backend
    deploy_lambdas
    deploy_frontend
}

destroy_aws() {
    # Terraform also destroys what depends on these two: CloudFront, the HTTP API with its VPC
    # link, Cloud Map and the chat agent runtime. Deleting a CloudFront distribution takes minutes.
    echo ">> Destroying AWS resources (frontend, CloudFront, backend, HTTP API, chat agent; Lambdas, DynamoDB data, Cognito, S3 receipts, SQS are kept: they cost nothing while idle)..."
    cd "${SCRIPT_DIR}/terraform"
    terraform init
    terraform destroy -target=module.frontend_bucket -target=module.backend_ecs \
        -var force_destroy_buckets=true -auto-approve
}

case "$ENV_NAME" in
    local)
        deploy_local
        ;;
    prod|aws)
        case "$ACTION" in
            up)   deploy_aws ;;
            down|destroy) destroy_aws ;;
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
