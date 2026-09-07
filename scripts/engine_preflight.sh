#!/usr/bin/env bash
# ==========================================================================================
#  engine_preflight.sh — refuse to start an engine that cannot fit
# ==========================================================================================
#
#  WHY THIS EXISTS. Starting a 7B engine on a card that has no room does not fail
#  fast. vLLM wedges at "Starting to load model" with no error line for fifteen
#  minutes, because a CUDA allocator waiting on memory that will never arrive has
#  nothing to report. SGLang gets OOM-killed with exit 137 — sometimes only after
#  it has been serving for a while, the moment another browser tab is opened.
#
#  Both of those cost twenty minutes and teach you nothing. This check costs two
#  seconds and names the fix.
#
#  IDEMPOTENCY. An engine that is ALREADY RUNNING has already paid its memory
#  cost. Re-asking "is there room to load it?" against the memory it is itself
#  holding would refuse a WORKING stack, so a running engine short-circuits to
#  success. `make up` on a live stack must be a no-op, not a failure.
#
#  Usage:  engine_preflight.sh <engine>          # vllm | sglang
#  Env:    SKIP_MEM_CHECK=1   bypass entirely (you accept the risk)
#
#  Exit: 0 = safe to start (or already running)   1 = would not fit
# ------------------------------------------------------------------------------------------
set -uo pipefail

ENGINE="${1:-sglang}"
CONTAINER="tp-${ENGINE}"

# Weights on disk for a 7B AWQ INT4 checkpoint, in MiB. The real need is larger:
# CUDA context, the KV cache, and allocator fragmentation all come out of the
# same budget. 1.4x + 1500MiB is the multiplier measured on this class of card.
WEIGHTS_MIB="${WEIGHTS_MIB:-5500}"
NEED_MIB=$(( (WEIGHTS_MIB * 14 / 10) + 1500 ))

say() { printf '  %s\n' "$*"; }

if [ "${SKIP_MEM_CHECK:-0}" = "1" ]; then
  say "preflight SKIPPED (SKIP_MEM_CHECK=1)"
  exit 0
fi

# -- already running? then it has already paid its memory cost -----------------
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
  say "preflight skipped: $CONTAINER is already running"
  exit 0
fi

# -- is there a GPU at all? ----------------------------------------------------
if ! nvidia-smi -L >/dev/null 2>&1; then
  echo ""
  say "NO NVIDIA GPU is visible."
  say "A local engine cannot start. Use the hosted chain instead:"
  say "    make up ENGINE=none          # SERVING_CHAIN=groq,openai"
  echo ""
  exit 1
fi

FREE_MIB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
TOTAL_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
[ -z "${FREE_MIB:-}" ] && { say "could not read GPU memory; skipping preflight"; exit 0; }

say "GPU: ${FREE_MIB} MiB free of ${TOTAL_MIB} MiB — ${ENGINE} needs ~${NEED_MIB} MiB"

if [ "$FREE_MIB" -ge "$NEED_MIB" ]; then
  say "preflight PASSED"
  exit 0
fi

# -- it will not fit: say why, and what to do about it -------------------------
echo ""
say "REFUSING TO START ${ENGINE}: not enough free VRAM."
echo ""
say "    free   ${FREE_MIB} MiB"
say "    needed ~${NEED_MIB} MiB  (${WEIGHTS_MIB} MiB weights x1.4 + 1500 MiB runtime)"
echo ""

# The commonest cause on a shared workstation is ANOTHER engine holding the card.
OTHER=$(docker ps --format '{{.Names}}' 2>/dev/null \
        | while read -r n; do
            docker inspect -f '{{range .HostConfig.DeviceRequests}}{{.Driver}}{{end}}' "$n" 2>/dev/null \
              | grep -q nvidia && [ "$n" != "$CONTAINER" ] && echo "$n"
          done)
if [ -n "$OTHER" ]; then
  say "  ANOTHER CONTAINER IS HOLDING THE GPU:"
  echo "$OTHER" | while read -r n; do say "      $n"; done
  say "  One GPU is one engine. Stop it first, e.g.:"
  echo "$OTHER" | while read -r n; do say "      docker stop $n"; done
  echo ""
fi

say "  Other remedies, cheapest first:"
say "    1. close GPU-heavy desktop apps (browsers hold hundreds of MiB each)"
say "    2. lower the memory fraction in .env"
say "         SGLANG_MEM_FRACTION (fraction of TOTAL)"
say "         VLLM_GPU_MEMORY_UTILIZATION (fraction of FREE)"
say "    3. shorten the context: SGLANG_MAX_MODEL_LEN / VLLM_MAX_MODEL_LEN"
say "    4. run hosted-only:  make up ENGINE=none"
say "    5. override this check:  make ${ENGINE}-up SKIP_MEM_CHECK=1"
echo ""
exit 1
