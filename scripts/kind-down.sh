#!/usr/bin/env bash
# Tear down the P6.2 local kind cluster entirely (all nodes, etcd state, PVCs).
# This is destructive and NOT the same as `make down` (which only stops compose
# containers and keeps their volumes) — anything only deployed in-cluster and
# not tracked in git/Helm values is gone after this.
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

set -a; [ -f .env ] && . ./.env; set +a
CLUSTER="${KIND_CLUSTER_NAME:-voyantra}"

if kind get clusters | grep -qx "$CLUSTER"; then
  echo "Deleting kind cluster '$CLUSTER' (all nodes + in-cluster state)..."
  kind delete cluster --name "$CLUSTER"
else
  echo "No kind cluster named '$CLUSTER' — nothing to do."
fi
