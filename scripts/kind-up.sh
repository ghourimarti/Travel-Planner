#!/usr/bin/env bash
# P6.2 one-command local bring-up on kind:
#   render config -> cluster -> build images (if missing) -> load into the node -> helm install.
# Run from anywhere. Reads .env for cluster shape (KIND_*) and OPENAI_API_KEY.
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

set -a; [ -f .env ] && . ./.env; set +a

CLUSTER="${KIND_CLUSTER_NAME:-voyantra}"
RELEASE="${KIND_CLUSTER_NAME:-voyantra}"
CHART=infra/helm/voyantra
TAG=p61
WORKER_COUNT="${KIND_WORKER_COUNT:-3}"
NODE_IMAGE="${KIND_NODE_IMAGE:-kindest/node:v1.31.2}"

# 1. render infra/kind/kind-config.yaml from the .tpl (worker count / node image from .env)
WORKER_NODES=""
for _ in $(seq 1 "$WORKER_COUNT"); do
  WORKER_NODES="${WORKER_NODES}  - role: worker
    image: ${NODE_IMAGE}
"
done
export KIND_CLUSTER_NAME="$CLUSTER" KIND_NODE_IMAGE="$NODE_IMAGE" WORKER_NODES
envsubst < infra/kind/kind-config.yaml.tpl > infra/kind/kind-config.yaml

# 2. cluster (idempotent — does NOT resize an already-running cluster; run
#    `make infra-down` first if you changed KIND_WORKER_COUNT/KIND_NODE_IMAGE)
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config infra/kind/kind-config.yaml
else
  echo "kind cluster '$CLUSTER' already exists — leaving node shape as-is."
  echo "(changed KIND_WORKER_COUNT or KIND_NODE_IMAGE? run 'make infra-down' first)"
fi

# 3. images: build only if absent, then side-load (kind has no registry)
docker image inspect "tp-api:$TAG"    >/dev/null 2>&1 || docker build -t "tp-api:$TAG"    -f apps/api/Dockerfile    .
docker image inspect "tp-worker:$TAG" >/dev/null 2>&1 || docker build -t "tp-worker:$TAG" -f apps/worker/Dockerfile .
docker image inspect "tp-web:$TAG"    >/dev/null 2>&1 || docker build -t "tp-web:$TAG"    -f apps/web/Dockerfile    ./apps/web
kind load docker-image "tp-api:$TAG" "tp-worker:$TAG" "tp-web:$TAG" --name "$CLUSTER"

# 4. install/upgrade and wait for readiness
helm upgrade --install "$RELEASE" "$CHART" \
  -f "$CHART/values-kind.yaml" \
  --set secrets.openaiApiKey="${OPENAI_API_KEY:-}" \
  --set api.replicas="${KIND_API_REPLICAS:-1}" \
  --set worker.replicas="${KIND_WORKER_REPLICAS:-1}" \
  --set web.replicas="${KIND_WEB_REPLICAS:-1}" \
  --wait --timeout 180s

kubectl get pods -l "app.kubernetes.io/instance=$RELEASE"
echo
echo "Port-forward:  kubectl port-forward svc/voyantra-api 8000:8000"
echo "               kubectl port-forward svc/voyantra-web 3000:3000"
