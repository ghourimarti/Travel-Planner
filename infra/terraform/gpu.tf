# GPU node group for self-hosted inference — SCALE-TO-ZERO BY DEFAULT.
#
# ============================================================================
#  STATUS: WRITTEN AND VALIDATED, NEVER PLANNED OR APPLIED.
#
#  `terraform fmt` and `terraform validate` pass, which proves the SYNTAX and the
#  provider schema — nothing more. It has never been run against a real AWS
#  account, so the instance type may be unavailable in the region, the quota may
#  be zero, and the AMI/taint interaction is unverified. Treat every number here
#  as a proposal until a `terraform plan` says otherwise.
#
#  This is the same category `scripts/bench_venue.py` was in before it ran: code
#  that lints clean and has never met reality. Marking it done would be the
#  "declared vs working" failure this project keeps finding.
# ============================================================================
#
# WHY min_size = 0
# ----------------
# A g5.xlarge is roughly $1/hour on demand — about $730/month left running. The
# whole reason to self-host is that inference becomes free at the margin, and a
# GPU idling overnight destroys that argument faster than any token bill. Zero is
# the only default that cannot surprise you.
#
# The cost of scale-to-zero is a cold start: the node must join, pull a ~30-50 GB
# engine image, and load ~5.5 GB of weights. Measured locally that load alone is
# 195 s (vLLM) to 435 s (SGLang), and the image pull is on top. Plan for minutes,
# not seconds — which is exactly why the serving chain has hosted legs behind the
# local one rather than treating the GPU as always-available.
#
# WHY A TAINT
# -----------
# Without it the scheduler will happily place the API, the worker and Postgres on
# your most expensive node. The taint makes GPU capacity opt-in: only pods that
# explicitly tolerate `nvidia.com/gpu` land here.

variable "gpu_enabled" {
  description = "Create the GPU node group at all. false = the group is not created, which is the shipped default: a GPU you forgot about is a recurring bill, not a mistake you notice once."
  type        = bool
  default     = false
}

variable "gpu_instance_type" {
  description = "GPU instance type. g5.xlarge = 1x A10G 24GB, which fits a 7B at INT4 with room the RTX 3060 does not have. VERIFY REGIONAL AVAILABILITY AND QUOTA — G-instance quota is zero on new accounts by default."
  type        = string
  default     = "g5.xlarge"
}

variable "gpu_min_size" {
  description = "Minimum GPU nodes. 0 = scale to zero when idle. Raise only if a cold start of several minutes is unacceptable, and price that decision first."
  type        = number
  default     = 0
}

variable "gpu_max_size" {
  description = "Maximum GPU nodes. Deliberately small: this is a spend ceiling as much as a capacity one."
  type        = number
  default     = 1
}

variable "gpu_desired_size" {
  description = "Desired GPU nodes at create time. 0 so applying this costs nothing until something scales it up."
  type        = number
  default     = 0
}

locals {
  # A node group with a GPU taint that nothing tolerates is dead capacity. The
  # Helm chart must add a matching toleration + nodeSelector before an engine
  # pod can ever land here — NOT yet wired, see update_todos.md.
  gpu_node_group = var.gpu_enabled ? {
    gpu = {
      instance_types = [var.gpu_instance_type]
      min_size       = var.gpu_min_size
      max_size       = var.gpu_max_size
      desired_size   = var.gpu_desired_size

      # GPU-optimised AMI: ships the NVIDIA driver and container runtime, so the
      # cluster does not also need a driver DaemonSet to be useful.
      ami_type = "AL2_x86_64_GPU"

      # Root volume sized for the engine images, which are the surprise here:
      # lmsysorg/sglang is 52 GB and vllm/vllm-openai is 31 GB locally. A default
      # 20 GB root disk cannot pull either, and the failure looks like a stuck
      # node rather than a full disk.
      disk_size = 200

      labels = {
        "workload" = "inference"
      }

      taints = {
        gpu = {
          key    = "nvidia.com/gpu"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled"       = "true"
        "k8s.io/cluster-autoscaler/${local.name}" = "owned"
        # The autoscaler cannot know a zero-sized group's capacity without being
        # told, so scale-from-zero needs these hints or it will never scale up.
        "k8s.io/cluster-autoscaler/node-template/label/workload"           = "inference"
        "k8s.io/cluster-autoscaler/node-template/taint/nvidia.com/gpu"     = "true:NoSchedule"
        "k8s.io/cluster-autoscaler/node-template/resources/nvidia.com/gpu" = "1"
      }
    }
  } : {}
}

output "gpu_node_group_enabled" {
  description = "Whether the GPU node group is created. Surfaced so a plan diff makes an expensive change obvious rather than incidental."
  value       = var.gpu_enabled
}

output "gpu_node_group_config" {
  description = "The GPU node group definition, for merging into module.eks eks_managed_node_groups. NOT yet merged — see the note below."
  value       = local.gpu_node_group
}

# ============================================================================
#  NOT WIRED INTO module.eks YET, AND DELIBERATELY SO.
#
#  Merging this into eks.tf's `eks_managed_node_groups` is one line:
#
#      eks_managed_node_groups = merge({ default = {...} }, local.gpu_node_group)
#
#  It is left unmerged because that line changes a resource that currently
#  exists in state, and I cannot run `terraform plan` to see what it would do.
#  Editing a live node group definition blind is how a cluster gets replaced
#  rather than updated. Merge it under a plan you can read.
# ============================================================================
