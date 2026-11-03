#!/usr/bin/env bash
# Send requests to the backend running on ECS (or any URL).
#
# Usage:
#   scripts/api.sh health
#   scripts/api.sh list
#   scripts/api.sh get <id>
#   scripts/api.sh create [store] [total]
#   scripts/api.sh delete <id>
#   scripts/api.sh summary
#   scripts/api.sh ip                       # print the current task public IP
#   scripts/api.sh raw <METHOD> <path> [json-body]
#
# Env overrides: BASE_URL (skips the ECS lookup), AWS_REGION, CLUSTER, SERVICE

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="${SCRIPT_DIR}/../terraform"
REGION="${AWS_REGION:-eu-west-1}"
PORT="${PORT:-8000}"

tf_out() { terraform -chdir="$TF_DIR" output -raw "$1" 2>/dev/null || true; }

task_ip() {
    local cluster="${CLUSTER:-$(tf_out backend_cluster_name)}"
    local service="${SERVICE:-$(tf_out backend_service_name)}"
    [[ -n "$cluster" && -n "$service" ]] || { echo "Error: cluster/service unknown (set CLUSTER and SERVICE)" >&2; exit 1; }

    local task eni ip
    task=$(aws ecs list-tasks --region "$REGION" --cluster "$cluster" --service-name "$service" \
        --desired-status RUNNING --query 'taskArns[0]' --output text)
    [[ "$task" != "None" && -n "$task" ]] || { echo "Error: no running task in $service" >&2; exit 1; }
    eni=$(aws ecs describe-tasks --region "$REGION" --cluster "$cluster" --tasks "$task" \
        --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)
    ip=$(aws ec2 describe-network-interfaces --region "$REGION" --network-interface-ids "$eni" \
        --query 'NetworkInterfaces[0].Association.PublicIp' --output text)
    echo "$ip"
}

cmd="${1:-}"
[[ -n "$cmd" ]] || { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
shift

if [[ "$cmd" == "ip" ]]; then task_ip; exit 0; fi

BASE_URL="${BASE_URL:-http://$(task_ip):${PORT}}"
echo ">> $BASE_URL" >&2

req() { # method path [body]
    local method="$1" path="$2" body="${3:-}"
    local -a args=(-sS -m 15 -X "$method" -w '\nHTTP %{http_code}\n' "${BASE_URL}${path}")
    [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' -d "$body")
    curl "${args[@]}"
}

case "$cmd" in
    health)  req GET /health ;;
    list)    req GET /expenses/ ;;
    summary) req GET /expenses/monthly-summary ;;
    get)     req GET "/expenses/${1:?id required}" ;;
    delete)  req DELETE "/expenses/${1:?id required}" ;;
    create)
        store="${1:-Silpo}"; total="${2:-42.5}"
        req POST /expenses/ "{\"date\":\"$(date +%F)\",\"store\":\"${store}\",\"items\":[{\"name\":\"Item\",\"price\":${total}}],\"total\":${total},\"notes\":\"created by api.sh\"}"
        ;;
    raw)     req "${1:?method required}" "${2:?path required}" "${3:-}" ;;
    *)       echo "Unknown command: $cmd" >&2; exit 1 ;;
esac
