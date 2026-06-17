#!/usr/bin/env bash
# P6.2 one-command local bring-up on kind:
#   cluster -> build images (if missing) -> load into the node -> helm install.
# Run from anywhere; reads OPENAI_API_KEY from the environment (.env not auto-loaded).
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

CLUSTER=voyantra
RELEASE=voyantra
CHART=infra/helm/voyantra
TAG=p61

# 1. cluster (idempotent)
if ! kind get clusters | grep -qx "$CLUSTER"; then
  kind create cluster --config infra/kind/kind-config.yaml
fi

# 2. images: build only if absent, then side-load (kind has no registry)
docker image inspect "tp-api:$TAG"    >/dev/null 2>&1 || docker build -t "tp-api:$TAG"    -f apps/api/Dockerfile    .
docker image inspect "tp-worker:$TAG" >/dev/null 2>&1 || docker build -t "tp-worker:$TAG" -f apps/worker/Dockerfile .
docker image inspect "tp-web:$TAG"    >/dev/null 2>&1 || docker build -t "tp-web:$TAG"    -f apps/web/Dockerfile    ./apps/web
kind load docker-image "tp-api:$TAG" "tp-worker:$TAG" "tp-web:$TAG" --name "$CLUSTER"

# 3. install/upgrade and wait for readiness
helm upgrade --install "$RELEASE" "$CHART" \
  -f "$CHART/values-kind.yaml" \
  --set secrets.openaiApiKey="${OPENAI_API_KEY:-}" \
  --wait --timeout 180s

kubectl get pods -l "app.kubernetes.io/instance=$RELEASE"
echo
echo "Port-forward:  kubectl port-forward svc/voyantra-api 8000:8000"
echo "               kubectl port-forward svc/voyantra-web 3000:3000"
