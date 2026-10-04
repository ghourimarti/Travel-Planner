#!/usr/bin/env bash
# ==========================================================================================
#  engine_preflight.sh — refuse to start an engine that cannot fit, and say how to fix it
# ==========================================================================================
#
#  WHY THIS EXISTS. Starting a 7B engine on a card that has no room does not fail
#  fast. vLLM wedges at "Starting to load model" with no error line, because a CUDA
#  allocator waiting on memory that will never arrive has nothing to report. SGLang
#  raises "Not enough memory" only after loading - or gets OOM-killed later, the moment
#  another browser tab is opened. This check costs two seconds and names the fix.
#
#  EACH ENGINE'S REAL RULE (not one number for both). The first version demanded a
#  flat 9200 MiB for either engine, whatever fraction was configured - so its own
#  advice to "lower the fraction" could never make it pass, and for SGLang that advice
#  was backwards. Both rules below are MEASURED on this card, not recalled:
#
#    SGLang  --mem-fraction-static is a share of the memory FREE at startup
#            (sglang 0.5.19: pre_model_load_memory = get_available_gpu_memory();
#            weights + KV pool = fraction x that). Log proof, 2026-09-29:
#              free 10.95 GB x 0.55 = 6.02 GB = 5.38 GB weights + 0.64 GB KV cache
#            What is left OUTSIDE the fraction must hold activations + CUDA graphs.
#            => too little free memory: RAISE the fraction; too high: activations OOM.
#
#    vLLM    --gpu-memory-utilization is a share of TOTAL memory and must fit in what
#            is free. Log proof: "Free memory on device (10.98/12.0 GiB) on startup.
#            Desired GPU memory utilization is (0.8, 9.6 GiB)".
#            => too little free memory: LOWER the fraction.
#
#  IDEMPOTENCY. An engine ALREADY RUNNING with the configured fraction and context has
#  paid its memory cost, so it short-circuits to success: `make up` on a live stack is a
#  no-op. Running with DIFFERENT values, compose is about to RECREATE it - and this check
#  used to skip exactly then, so new settings reached the GPU unchecked (found
#  2026-09-29: 0.55 -> 0.75). Now it stops the old engine first (compose would anyway),
#  measures the memory that frees, and on a refusal restarts the old engine on its old
#  settings, so a bad value never costs the engine you had.
#
#  Usage:  engine_preflight.sh <engine>          # vllm | sglang
#  Env:    SKIP_MEM_CHECK=1   bypass entirely (you accept the risk)
#  Exit:   0 = safe to start (or already running as configured)   1 = would not fit
# ------------------------------------------------------------------------------------------
set -uo pipefail

ENGINE="${1:-sglang}"
CONTAINER="tp-${ENGINE}"

say() { printf '  %s\n' "$*"; }

# -- measured constants (RTX 3060, Qwen2.5-7B-Instruct-AWQ) ---------------------------
SGLANG_WEIGHTS_MIB="${SGLANG_WEIGHTS_MIB:-5510}"  # SGLang: "Load weight end ... mem usage=5.38 GB"
VLLM_WEIGHTS_MIB="${VLLM_WEIGHTS_MIB:-5693}"      # vLLM: 5.56 GiB weights + non-torch
ACT_MIB="${ACT_MIB:-1536}"                        # vLLM: 1.04 GiB activation + 0.47 GiB graphs
CTX_OVERHEAD_MIB="${CTX_OVERHEAD_MIB:-500}"       # CUDA context created before the engine measures
KV_KIB_PER_TOKEN=56                               # 28 layers x 4 KV heads x 128 dim x K,V x fp16

if [ "${SKIP_MEM_CHECK:-0}" = "1" ]; then
  say "preflight SKIPPED (SKIP_MEM_CHECK=1)"
  exit 0
fi

# -- the values the engine will ACTUALLY get: environment (make) > .env > default -------
_sg_frac="${SGLANG_MEM_FRACTION-}"; _vl_frac="${VLLM_GPU_MEMORY_UTILIZATION-}"
_sg_ctx="${SGLANG_MAX_MODEL_LEN-}"; _vl_ctx="${VLLM_MAX_MODEL_LEN-}"
if [ -f .env ]; then set -a; . ./.env 2>/dev/null || true; set +a; fi
[ -n "$_sg_frac" ] && SGLANG_MEM_FRACTION="$_sg_frac"
[ -n "$_vl_frac" ] && VLLM_GPU_MEMORY_UTILIZATION="$_vl_frac"
[ -n "$_sg_ctx" ] && SGLANG_MAX_MODEL_LEN="$_sg_ctx"
[ -n "$_vl_ctx" ] && VLLM_MAX_MODEL_LEN="$_vl_ctx"

if [ "$ENGINE" = "sglang" ]; then
  FRAC="${SGLANG_MEM_FRACTION:-0.75}"; CTX="${SGLANG_MAX_MODEL_LEN:-8192}"; FLAG="SGLANG_MEM_FRACTION"
  FRAC_ARG="--mem-fraction-static"; CTX_ARG="--context-length"
else
  FRAC="${VLLM_GPU_MEMORY_UTILIZATION:-0.80}"; CTX="${VLLM_MAX_MODEL_LEN:-8192}"; FLAG="VLLM_GPU_MEMORY_UTILIZATION"
  FRAC_ARG="--gpu-memory-utilization"; CTX_ARG="--max-model-len"
fi
KV_MIN_MIB=$(( CTX * KV_KIB_PER_TOKEN / 1024 ))  # room for ONE full-context request

# The value that follows a flag in the RUNNING container's command line.
running_arg() {
  docker inspect -f '{{join .Config.Cmd " "}}' "$CONTAINER" 2>/dev/null \
    | awk -v f="$1" '{ for (i = 1; i < NF; i++) if ($i == f) { print $(i + 1); exit } }'
}
same_number() { awk -v a="$1" -v b="$2" 'BEGIN { exit !(a + 0 == b + 0) }'; }
gpu_free() {
  nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '
}

# -- already running? skip ONLY if it runs with the values compose would give it --------
RESTART_ON_REFUSAL=0
if docker ps --format '{{.Names}}' 2>/dev/null | grep -qx "$CONTAINER"; then
  RUN_FRAC=$(running_arg "$FRAC_ARG"); RUN_CTX=$(running_arg "$CTX_ARG")
  if [ -z "$RUN_FRAC" ] || [ -z "$RUN_CTX" ] \
     || { same_number "$RUN_FRAC" "$FRAC" && same_number "$RUN_CTX" "$CTX"; }; then
    say "preflight skipped: $CONTAINER is already running with these settings"
    exit 0
  fi
  say "$CONTAINER runs ${FRAC_ARG} ${RUN_FRAC} / ${CTX_ARG} ${RUN_CTX}; the target is ${FRAC} / ${CTX}."
  say "compose will RECREATE it - stopping it first, so this check measures the memory it frees."
  BEFORE_MIB=$(gpu_free)
  docker stop "$CONTAINER" >/dev/null 2>&1 || true
  # CUDA hands memory back over a few seconds, not at once: stopping at the FIRST rise
  # measured 9,322 MiB where the new engine then saw ~10.9 GB (2026-09-29). So wait until
  # it has risen AND two readings a second apart agree - at most 15 s.
  PREV_MIB=""
  for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    NOW_MIB=$(gpu_free)
    if [ -n "$NOW_MIB" ] && [ -n "$BEFORE_MIB" ] && [ -n "$PREV_MIB" ] \
       && [ "$NOW_MIB" -gt $(( BEFORE_MIB + 1024 )) ] && [ $(( NOW_MIB - PREV_MIB )) -lt 128 ]; then
      break
    fi
    PREV_MIB="$NOW_MIB"
    sleep 1
  done
  RESTART_ON_REFUSAL=1
fi

# -- is there a GPU at all? ----------------------------------------------------
if ! nvidia-smi -L >/dev/null 2>&1; then
  echo ""
  say "NO NVIDIA GPU is visible."
  say "A local engine cannot start. Use the hosted chain instead:"
  say "    make up          # SERVING_CHAIN=groq,openai"
  echo ""
  exit 1
fi

FREE_MIB=$(gpu_free)
TOTAL_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' ')
[ -z "${FREE_MIB:-}" ] && { say "could not read GPU memory; skipping preflight"; exit 0; }

# All the arithmetic in one awk call: fractions are decimals, bash is integer-only.
# Prints: verdict budget need low high  (verdict: ok | too_low | too_high | no_room)
read -r VERDICT BUDGET NEED LOW HIGH < <(awk \
  -v e="$ENGINE" -v f="$FRAC" -v free="$FREE_MIB" -v total="$TOTAL_MIB" \
  -v ctxo="$CTX_OVERHEAD_MIB" -v act="$ACT_MIB" -v kv="$KV_MIN_MIB" \
  -v sgw="$SGLANG_WEIGHTS_MIB" -v vlw="$VLLM_WEIGHTS_MIB" 'BEGIN {
    if (e == "sglang") {
      eff = free - ctxo; need = sgw + kv; budget = f * eff
      low = need / eff; high = 1 - act / eff
      if (low > high)            v = "no_room"
      else if (budget < need)    v = "too_low"
      else if (eff - budget < act) v = "too_high"
      else                       v = "ok"
    } else {
      need = vlw + act + kv; budget = f * total
      low = need / total; high = (free - 128) / total      # 128: jitter margin
      if (low > high)            v = "no_room"
      else if (budget > free - 128) v = "too_high"
      else if (budget < need)    v = "too_low"
      else                       v = "ok"
    }
    printf "%s %d %d %.2f %.2f\n", v, budget, need, low, high
  }')

say "GPU: ${FREE_MIB} MiB free of ${TOTAL_MIB} MiB"
if [ "$ENGINE" = "sglang" ]; then
  say "sglang: ${FLAG}=${FRAC} is a share of FREE memory -> ${BUDGET} MiB for weights + KV"
  say "        needs >= ${NEED} MiB (${SGLANG_WEIGHTS_MIB} weights + ${KV_MIN_MIB} KV for ${CTX} tokens),"
  say "        and ~${ACT_MIB} MiB left OUTSIDE it for activations + CUDA graphs"
else
  say "vllm:   ${FLAG}=${FRAC} is a share of TOTAL memory -> ${BUDGET} MiB, must fit in free"
  say "        needs >= ${NEED} MiB (weights + activations/graphs + ${KV_MIN_MIB} KV for ${CTX} tokens)"
fi

if [ "$VERDICT" = "ok" ]; then
  say "preflight PASSED"
  exit 0
fi

# -- it will not fit: say why, which way to move, and to what ----------------------
MID=$(awk -v a="$LOW" -v b="$HIGH" 'BEGIN { printf "%.2f", (a + b) / 2 }')
echo ""
case "$VERDICT" in
  too_low)
    say "REFUSING TO START ${ENGINE}: ${FLAG}=${FRAC} is too LOW for the memory free right now."
    say "  -> RAISE it: set ${FLAG}=${MID} in .env  (anything from ${LOW} to ${HIGH} fits now)" ;;
  too_high)
    say "REFUSING TO START ${ENGINE}: ${FLAG}=${FRAC} is too HIGH for the memory free right now."
    say "  -> LOWER it: set ${FLAG}=${MID} in .env  (anything from ${LOW} to ${HIGH} fits now)" ;;
  no_room)
    SHORT=$(awk -v l="$LOW" -v h="$HIGH" -v t="$TOTAL_MIB" 'BEGIN { printf "%d", (l - h) * t + 1 }')
    say "REFUSING TO START ${ENGINE}: no ${FLAG} value fits - the card is too full right now."
    say "  -> free roughly ${SHORT}+ MiB of VRAM first (no fraction can make this fit)" ;;
esac
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

say "  Other remedies:"
say "    - close GPU-heavy desktop apps (browsers hold hundreds of MiB each), then retry"
say "    - run hosted-only:        make up"
say "    - override this check:    make ${ENGINE}-up SKIP_MEM_CHECK=1"
echo ""
if [ "$RESTART_ON_REFUSAL" = "1" ]; then
  # A refused NEW value must not cost the engine you had: `docker start` brings back the
  # stopped container exactly as it was (compose only recreates on `up`).
  docker start "$CONTAINER" >/dev/null 2>&1 \
    && say "  restarted $CONTAINER on its OLD settings (${FRAC_ARG} ${RUN_FRAC}); nothing changed" \
    || say "  could NOT restart $CONTAINER - start it with: docker start $CONTAINER"
  echo ""
fi
exit 1
