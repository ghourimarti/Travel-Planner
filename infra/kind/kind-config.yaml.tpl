# Local kind cluster for P6.2 — single node is enough to exercise the chart
# (scheduling, Services, in-cluster DNS, PVCs). We reach workloads via
# `kubectl port-forward`, so no host extraPortMappings are needed.
#
# Template rendered by scripts/kind-up.sh via envsubst -> infra/kind/kind-config.yaml
# (the rendered file is gitignored; edit THIS .tpl, not the generated one).
# Node count/image are controlled from .env: KIND_WORKER_COUNT, KIND_NODE_IMAGE.
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: ${KIND_CLUSTER_NAME}
# control-plane + N workers: lets us see real pod scheduling spread across
# nodes (the control-plane is tainted, so app pods land on the workers).
# All nodes pinned to k8s 1.31 by default — this Docker/WSL2 host runs cgroup v1, which the
# kubelet in k8s 1.32+ hard-rejects. 1.31 still tolerates it, so the cluster
# comes up without reconfiguring the host (cgroup-v2 upgrade tracked separately).
nodes:
  - role: control-plane
    image: ${KIND_NODE_IMAGE}
${WORKER_NODES}
