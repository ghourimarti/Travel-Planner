#!/usr/bin/env bash
# ==========================================================================================
#  engine_failed.sh — say WHY an engine did not come up, by inspecting it
# ==========================================================================================
#
#  WHY THIS EXISTS. The obvious version of this message asserts a cause:
#      "The container is still running — this is a timeout, not a crash."
#  The one time that matters, it is wrong. A SIGKILLed container is gone, and the
#  message sends you to tail logs that no longer exist and to raise a timeout that
#  could never have helped.
#
#  A diagnostic that guesses is worse than no diagnostic, because it is believed.
#  This one BRANCHES on the container's actual state.
#
#  Usage:  engine_failed.sh <engine> [wait_seconds]
# ------------------------------------------------------------------------------------------
set -uo pipefail

ENGINE="${1:-sglang}"
WAITED="${2:-900}"
CONTAINER="tp-${ENGINE}"

say() { printf '  %s\n' "$*"; }

echo ""
say "=============================================================="
say " ${ENGINE} did not reach SERVING within ${WAITED}s"
say "=============================================================="
echo ""

STATE=$(docker inspect -f '{{.State.Status}}' "$CONTAINER" 2>/dev/null || echo "gone")
EXITCODE=$(docker inspect -f '{{.State.ExitCode}}' "$CONTAINER" 2>/dev/null || echo "")
OOM=$(docker inspect -f '{{.State.OOMKilled}}' "$CONTAINER" 2>/dev/null || echo "")

case "$STATE" in

  running)
    say "STATE: running — this is a genuine TIMEOUT, not a crash."
    say "The engine is alive and still loading. The commonest cause is a cold"
    say "weight download: ~5.5GB, and huggingface_hub does NOT resume across"
    say "process restarts, so an interrupted pull restarts from byte zero."
    echo ""
    say "  watch it finish:   docker logs -f $CONTAINER"
    say "  give it longer:    make ${ENGINE}-up ENGINE_WAIT=3600"
    say "  bytes on disk:     docker exec $CONTAINER du -sh /root/.cache/huggingface"
    echo ""
    say "DO NOT interrupt a download in progress to 'retry' it."
    ;;

  exited|dead)
    if [ "$OOM" = "true" ] || [ "$EXITCODE" = "137" ]; then
      say "STATE: exited ${EXITCODE} — OUT OF MEMORY (OOMKilled=${OOM})."
      echo ""
      nvidia-smi --query-gpu=memory.total,memory.used,memory.free \
                 --format=csv 2>/dev/null | sed 's/^/      /'
      echo ""
      say "  Exit 137 is a KILL, and it has two different causes:"
      say "    GPU VRAM  — the model did not fit on the card"
      say "    HOST RAM  — WSL2 caps the Docker VM at half of host RAM by default,"
      say "                and the engine starts LAST, so it is what gets taken."
      echo ""
      say "  Remedies:"
      say "    1. stop whatever else holds the GPU (another project's engine counts)"
      say "    2. lower SGLANG_MEM_FRACTION / VLLM_GPU_MEMORY_UTILIZATION in .env"
      say "    3. shorten SGLANG_MAX_MODEL_LEN / VLLM_MAX_MODEL_LEN"
      say "    4. raise the WSL2 VM ceiling in %USERPROFILE%\\.wslconfig, then"
      say "       'wsl --shutdown' to apply:"
      say "           [wsl2]"
      say "           memory=22GB"
      say "           autoMemoryReclaim=gradual"
    else
      say "STATE: exited ${EXITCODE} — the engine CRASHED."
      echo ""
      say "  last 40 log lines:"
      docker logs --tail 40 "$CONTAINER" 2>&1 | sed 's/^/      /'
    fi
    ;;

  gone|"")
    say "STATE: the container does not exist."
    say "It was never created, or it was removed after failing."
    echo ""
    say "  Compose may have refused to start it. Re-run without --wait to see:"
    say "      docker compose -f docker-compose.gpu.yml --profile gpu-${ENGINE} up ${ENGINE}"
    ;;

  *)
    say "STATE: ${STATE} (exit=${EXITCODE}, oom=${OOM})"
    docker logs --tail 30 "$CONTAINER" 2>&1 | sed 's/^/      /'
    ;;
esac

echo ""
say "Full runbook: docs/gpu-venue.md"
echo ""
