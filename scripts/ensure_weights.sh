#!/usr/bin/env bash
# Pre-stage model weights into the shared HF cache volume, resumably.
#
# WHY THIS EXISTS
# ---------------
# Letting the ENGINE download its own weights conflates two failures that need
# different responses: "the model is still loading" and "the download died".
# Worse, it does it while HOLDING THE GPU, so a stalled download parks the card
# for as long as nobody notices.
#
# This was not a theoretical concern. On the first cold start here the engine
# reached 0.87 GB of 5.5 GB and then transferred ZERO bytes for six minutes while
# the container sat `unhealthy` and kept the card reserved. Unauthenticated HF
# downloads are rate-limited and can hang without ever erroring.
#
# So: fetch the weights in a throwaway container with NO --gpus, verify progress,
# and only then start the engine. A cold start becomes a fast load.
#
# XET IS DISABLED ON PURPOSE
# --------------------------
# huggingface_hub >=1.x ships `hf_xet` and uses the Xet chunk backend by default.
# On this network it hangs: the process stays alive, writes 0-byte .incomplete
# placeholders, and transfers NOTHING, indefinitely. Measured A/B on the same
# container, same token, same file:
#
#     Xet enabled (default) ......  0 MB in 120 s
#     HF_HUB_DISABLE_XET=1 ......  21 MB in  90 s   (matches raw curl, ~0.2 MB/s)
#
# The classic HTTP path is slow here but it MOVES, and a slow transfer finishes
# while a silent one never does. Note this is not a rate-limit problem: an
# authenticated token changed throughput by nothing (0.19 -> 0.23 MB/s).
#
# RESUME
# ------
# huggingface_hub writes `<blob>.<hash>.incomplete` and resumes from it, so a
# killed download costs only the bytes in flight -- PROVIDED the cache volume is
# not deleted. Never `docker volume prune` (see docs/gpu-venue.md).
#
# STALL DETECTION
# ---------------
# A hung transfer looks identical to a slow one from the outside, so we do not
# guess: the cache is sampled on an interval and sustained zero growth is treated
# as death and retried. Retrying is safe precisely because it resumes.
#
# It takes STALL_STRIKES *consecutive* quiet windows, not one. An unauthenticated
# HF client spends minutes in rate-limit backoff before a byte moves, so a
# single-window trigger kills healthy transfers and the loop thrashes without ever
# finishing a file. Impatient detection is its own failure mode.
set -euo pipefail

# Pick up HF_TOKEN (and model overrides) if the operator has set them. An
# authenticated pull gets materially higher rate limits, which is the actual cure
# for the stalls this script works around.
[ -f .env ] && { set -a; . ./.env 2>/dev/null || true; set +a; }

MODEL="${1:-${SGLANG_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}}"
IMAGE="${WEIGHTS_IMAGE:-lmsysorg/sglang:latest}"
ATTEMPTS="${WEIGHTS_ATTEMPTS:-8}"
STALL_S="${WEIGHTS_STALL_S:-120}"        # sampling interval
STALL_STRIKES="${WEIGHTS_STALL_STRIKES:-3}"  # consecutive quiet windows => dead

# The cache lives in a compose-project-prefixed volume. Find it rather than
# hardcoding a project name, so a renamed directory does not silently create a
# SECOND cache and re-download 5.5 GB into it.
VOL="$(docker volume ls --format '{{.Name}}' | grep -E '_tp_hf_cache$' | head -1 || true)"
if [ -z "$VOL" ]; then
  VOL="$(docker compose -f docker-compose.gpu.yml config --format json 2>/dev/null \
        | python -c "import sys,json;print(json.load(sys.stdin)['name']+'_tp_hf_cache')" 2>/dev/null || true)"
fi
[ -n "$VOL" ] || { echo "  cannot determine the HF cache volume name"; exit 1; }

cache_bytes() {
  docker run --rm -v "$VOL":/c alpine sh -c 'du -sb /c 2>/dev/null | cut -f1' 2>/dev/null || echo 0
}

# Say OUT LOUD whether this run is authenticated. An anonymous pull is rate-limited
# into a multi-hour crawl, and the failure mode is indistinguishable from a slow
# link -- so the one thing that must never happen is believing a token is in play
# when it is not.
if [ -n "${HF_TOKEN:-}" ]; then
  TOKEN_ARGS="-e HF_TOKEN=$HF_TOKEN"
  AUTH="AUTHENTICATED (token ...${HF_TOKEN: -4})"
else
  TOKEN_ARGS=""
  AUTH="ANONYMOUS -- rate-limited. Set HF_TOKEN in .env for a usable download rate."
fi

# FAST PATH. A warm cache must cost ~nothing: this script now runs before EVERY engine
# start, and an unconditional 2-minute sampling window would tax every bring-up to
# guard against a download that already happened. Complete means: at least one
# *.safetensors in the snapshot AND no *.incomplete anywhere.
if docker run --rm -v "$VOL":/c alpine sh -c      'ls /c/hub/models--*/snapshots/*/*.safetensors >/dev/null 2>&1 &&       [ -z "$(find /c -name "*.incomplete" -print -quit)" ]' 2>/dev/null; then
  echo "  weights already complete in $VOL - nothing to do"
  exit 0
fi

echo "  model  : $MODEL"
echo "  volume : $VOL"
echo "  auth   : $AUTH"
echo "  start  : $(( $(cache_bytes) / 1000000 )) MB already cached"
echo ""

for attempt in $(seq 1 "$ATTEMPTS"); do
  echo "  -- attempt $attempt/$ATTEMPTS ------------------------------------------"

  # No --gpus on purpose: downloading is not compute, and holding the card while
  # fetching 5.5 GB is what wedged the first attempt.
  docker run -d --rm --name tp-weights \
    -v "$VOL":/root/.cache/huggingface \
    -e HF_HUB_ENABLE_HF_TRANSFER=0 \
    -e HF_HUB_DISABLE_XET=1 \
    $TOKEN_ARGS \
    "$IMAGE" \
    python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('$MODEL', allow_patterns=['*.safetensors','*.json','*.txt','*.model'], max_workers=4)
print('SNAPSHOT_COMPLETE')
" >/dev/null

  last=$(cache_bytes); stalled=0; strikes=0
  while docker ps --format '{{.Names}}' | grep -qx tp-weights; do
    # Wait in SMALL steps so an exit is noticed within seconds, but only measure on
    # the STALL_S cadence: cache_bytes spawns a container, so sampling it every few
    # seconds would cost more than the download.
    waited=0
    while [ "$waited" -lt "$STALL_S" ]; do
      docker ps --format '{{.Names}}' | grep -qx tp-weights || break
      sleep 5
      waited=$(( waited + 5 ))
    done
    docker ps --format '{{.Names}}' | grep -qx tp-weights || break
    now=$(cache_bytes)
    delta=$(( now - last ))
    printf "     %6s MB cached  (+%s MB in %ss)\n" "$(( now / 1000000 ))" "$(( delta / 1000000 ))" "$STALL_S"
    if [ "$delta" -le 0 ]; then
      strikes=$(( strikes + 1 ))
      # REPORT ONLY -- NEVER KILL. Measured the hard way: this huggingface_hub
      # writes `<blob>.<session-id>.incomplete`, and a NEW process gets a NEW
      # session id and restarts that file from byte ZERO. Killing a slow transfer
      # therefore does not "retry from where it left off", it ORPHANS every
      # partial byte. An earlier version of this script killed on sustained
      # silence and drove net progress on a 4GB blob to exactly zero across three
      # cycles, while the un-babysat engine had managed 612 MB on its own.
      #
      # A slow link and a dead one are indistinguishable from cache growth alone,
      # so when the cost of being wrong is asymmetric -- and here it is, badly --
      # the detector reports and the human decides.
      echo "     quiet window ${strikes} (reporting only; a kill would orphan the partial)"
    else
      strikes=0
    fi
    last=$now
  done

  if [ "$stalled" -eq 0 ]; then
    if docker logs tp-weights 2>&1 | grep -q SNAPSHOT_COMPLETE; then :; fi
    # Container exited on its own. Verify by CONTENT, not by exit status: a
    # partial snapshot also exits 0 if the process was killed between files.
    if docker run --rm -v "$VOL":/c alpine sh -c \
         'ls /c/hub/models--*/snapshots/*/*.safetensors >/dev/null 2>&1'; then
      echo ""
      echo "  weights present: $(( $(cache_bytes) / 1000000 )) MB in $VOL"
      exit 0
    fi
    echo "     exited without a complete snapshot -> retrying"
  fi
done

echo ""
echo "  FAILED after $ATTEMPTS attempts. The partial download is KEPT and will resume."
echo "  If HF is rate-limiting you, set a token and re-run:"
echo "      HF_TOKEN=hf_xxx bash scripts/ensure_weights.sh"
exit 1
