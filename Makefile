# ==========================================================================================
#  VOYANTRA - AI TRAVEL PLANNER
# ==========================================================================================
#
#  Every section below has the same shape:
#      boxed title  ->  documentation  ->  the commands themselves
#
#  COMPOSITION RULE: a target that needs another tier CALLS THAT TIER'S TARGET.
#  `upv` is downv + app + migrate + seed + obs, not five copies of a docker compose
#  line. Change how the data tier starts in ONE place and every caller follows.
#
#  Quick start:
#      make help          every target
#      make bootstrap     from scratch: stores + schema + app + corpus
#      make full          everything in Docker (data + app + observability)
#      make urls          where each service lives
#      make check         the green gate (lint + types + tests)
# ==========================================================================================

.PHONY: api app audit cache-clear cache-ls cache-prefix metrics-note runs-clear down-compose up-app up-data up-obs audit-deps bench-engine bench-groq bench-openai bootstrap chaos check clean-models data down down-engine downv downv-overpass engine-guide eval eval-rag full help infra infra-down ingest install licenses lint load logs migrate observability ps sast secrets seed services sglang-down sglang-downv sglang-test sglang-up sglang-upv test typecheck up up-engine up-sglang up-vllm up-vllm-sglang up-with-engine upv urls vllm-down vllm-downv vllm-test vllm-up vllm-upv webui which-engine worker state-ls kind-start kind-stop kind-status kind-down kill-on kill-off kill-status inspect inspect-sglang inspect-vllm smoke weights-status weights-ensure gpu gpu-down cache-flush tf-init tf-validate tf-plan chart-lint images clean-images clean-all langfuse service_ls redisinsight-register

# `make` with no target prints the directory rather than running anything destructive.
.DEFAULT_GOAL := help

help:           ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'


# ==========================================================================================
#  1. VARIABLES
# ==========================================================================================
#  Every variable in this file is declared HERE and nowhere else.
#
#  DC is ONE docker compose invocation naming all three files. Tiers are selected by
#  SERVICE NAME (SVC_DATA / SVC_APP / SVC_OBS), never by which -f flags are passed.
#
#  It was the other way round once - a DC_APP that bundled the data file, because
#  docker-compose.app.yml has `depends_on: db/redis` and compose cannot resolve a
#  service no file defines. That made the file set do two jobs at once: "what compose
#  can see" and "what I want running". The result was `make app` silently starting
#  Postgres, with no way to ask for the app alone. Splitting the two jobs - one file
#  set for visibility, service lists for intent - is what fixes it, and it is why
#  `make up-app` can pass --no-deps and genuinely mean only api/worker/web.
#
#  SVC_DATA_WAIT is the health-gated subset. Overpass is excluded because its first
#  boot imports OSM for 2-4 hours, and `--wait` on that blocks every bring-up.
#
#  DATA_VOLS is what `make downv` wipes - every app/data store EXCEPT the Overpass DB,
#  so the multi-hour OSM import survives a routine wipe. Overpass is dropped only by
#  the separate `make downv-overpass`, because re-importing it costs 2-4 hours.
#
#  PROJECT_CMD asks Docker Compose for the project name at RUNTIME rather than deriving
#  it from the directory. This repo's path contains spaces and an `&`, which breaks
#  $(notdir $(CURDIR)); asking compose also keeps the prefix correct if the repo moves.
#
#  MYPY_PATHS is a variable rather than an inline list so the type-check target stays
#  one readable line and new packages are added in exactly one place.
# ------------------------------------------------------------------------------------------

# ONE canonical compose file set. Tiers are selected by SERVICE NAME (below), never
# by which -f flags are passed.
#
# WHY: docker-compose.app.yml declares `depends_on: db, redis`, so an app-ONLY file
# set does not parse - compose cannot resolve a service name that no file defines.
# The old DC_APP worked around that by including the data file, which is exactly why
# `make app` silently started Postgres. Scoping by file conflates "what compose can
# see" with "what I want running"; scoping by service separates them.
DC             := docker compose -f docker-compose.data.yml -f docker-compose.app.yml -f docker-compose.observability.yml

# The three tiers, by service. Adding a service to a compose file means adding it
# here too - a service in no list is a service no lifecycle target will ever start.
SVC_DATA       := db redis qdrant overpass
SVC_APP        := api worker web
SVC_OBS        := jaeger flower redisinsight prometheus grafana loki promtail alertmanager langfuse-web langfuse-worker langfuse-postgres langfuse-redis langfuse-clickhouse langfuse-minio

# Health-gated subset of the data tier. Overpass is EXCLUDED on purpose: its first
# boot imports OSM for 2-4 hours, so `--wait` on it would block every bring-up.
SVC_DATA_WAIT  := db redis qdrant

MYPY_PATHS     := packages/core/src packages/tools/src packages/agents/src \
                  apps/api/src apps/worker/src packages/eval/src packages/retrieval/src

DATA_VOLS      := tp_pgdata tp_qdrant \
                  langfuse_pgdata langfuse_minio_data \
                  langfuse_clickhouse_data langfuse_clickhouse_logs

PROJECT_CMD     = $(DC) config --format json | python -c "import sys,json;print(json.load(sys.stdin)['name'])"

# Load-test target. Override per-invocation: `make load BASE_URL=http://host:port`
BASE_URL       ?= http://localhost:8000

DC_GPU         := docker compose -f docker-compose.gpu.yml

# ENGINE picks the local inference engine AND the failover chain TOGETHER,
# because they are one decision. See section 2.
ENGINE         ?= sglang
# How long to wait for an engine to reach SERVING, weights ALREADY on disk.
# Measured: 435s worst observed for a 7B AWQ load + CUDA graph capture on an RTX 3060.
# This no longer has to cover a download - `ensure_weights.sh` runs first - which is
# what makes 900s an honest budget instead of an optimistic one.
ENGINE_WAIT    ?= 900

# kind lifecycle. KIND=0 makes every composite target ignore Kubernetes entirely.
#   up / upv  ->  kind-start   create if absent, else RESTART stopped nodes
#   down      ->  kind-stop    nodes stopped, CLUSTER AND STATE PRESERVED
#   downv     ->  kind-down    cluster deleted
# The cluster NAME comes from .env (KIND_CLUSTER_NAME, default 'voyantra') and every
# target below matches it with `grep -qx`, so a kind cluster belonging to a different
# project on the same machine can never be stopped or deleted by this Makefile.
KIND           ?= 1

# Tag for the three images kind side-loads. MUST match TAG in scripts/kind-up.sh:
# they are the same images, and a mismatch makes `make images` build artefacts the
# cluster then ignores while it builds its own.
IMAGE_TAG      ?= p61

# Is a GPU actually visible to docker? Detected, not assumed. Overridable for a
# dry run: `make up GPU=0` behaves exactly as it would on a machine without one.
GPU            ?= $(shell nvidia-smi -L >/dev/null 2>&1 && echo 1 || echo 0)
# Set to 1 to start an engine even when the memory preflight says it cannot fit.
SKIP_MEM_CHECK ?= 0
ALL_ENGINE_PROFILES := --profile gpu-vllm --profile gpu-sglang --profile webui


# ==========================================================================================
#  2. ENGINE / GPU PROFILE
# ==========================================================================================
#  ENGINE picks the local inference engine AND the failover chain together, because
#  they are ONE decision. Starting SGLang without naming it in SERVING_CHAIN - or
#  naming it without starting it - is the commonest way to believe you are
#  benchmarking a self-hosted engine while a hosted one quietly answers every request.
#  Two files, one knob.
#
#      ENGINE=sglang  (default)   local-sglang,groq,openai
#      ENGINE=vllm                local-vllm,groq,openai
#      ENGINE=none                groq,openai
#
#  ONE ENGINE AT A TIME, deliberately. There is no ENGINE=both: two engines on one
#  12GB card is a deadlock, not a configuration (vLLM 0.80 + SGLang 0.70 = 150% of
#  the card), and they are not independent failure domains anyway - both die with
#  the GPU. Independence begins at the hosted legs.
#
#  HOSTED ORDER IS BY PRICE - AND PRICE MUST BE COMPARED WITHIN A TIER.
#
#  The planner composes on MID and criticises on FRONTIER. It never composes on CHEAP,
#  which is the eval judge's tier. Compare the models each venue actually serves THERE:
#
#      MID / FRONTIER      openai  gpt-4o             $2.50 / $10.00  per 1M
#                          groq    qwen/qwen3.8-27b   $0.80 / $ 4.00  per 1M
#
#  So groq is ~2.8x CHEAPER on the path this app runs, and measurement agrees: the same
#  single-city plan cost $0.000816 via groq and $0.002659 via openai.
#
#  THE TRAP, RECORDED BECAUSE I FELL IN IT: openai's CHEAP model is gpt-4o-mini at
#  $0.15/$0.60, which is far cheaper than groq. Comparing that against groq's MID price
#  makes groq look 6x too expensive and inverts the whole chain. Both numbers are real;
#  the comparison is not. A cost table is only meaningful tier by tier.
#
#  OPENAI STAYS LAST because it is the leg that answers when everything else is down,
#  and because openai and groq fail independently - vendor diversity is the only thing a
#  second hosted leg genuinely buys.
#
#  WATCHING COST IS THE TRIPWIRE: while the GPU serves, cost reads $0. The moment a
#  hosted leg answers it climbs, and that transition is how you learn a local engine
#  died long before anyone reports a slow app.
# ------------------------------------------------------------------------------------------

ifeq ($(ENGINE),vllm)
  ENGINE_PROFILE := --profile gpu-vllm
  ENGINE_CHAIN   := local-vllm,groq,openai
  ENGINE_STOP    := sglang
  ENGINE_START   := vllm
  # Same values .env already carries, so this mode is unchanged.
  ENGINE_VLLM_FRAC   := 0.80
  ENGINE_SGLANG_FRAC := 0.55
  ENGINE_CTX         := 8192
  # In-network URL: the gpu tier shares THIS compose project, so the service name
  # resolves with no host port. Exported by up-with-engine so ENGINE= is authoritative.
  ENGINE_URL_ENV := VLLM_URL=http://vllm:8000/v1
else ifeq ($(ENGINE),sglang)
  ENGINE_PROFILE := --profile gpu-sglang
  ENGINE_CHAIN   := local-sglang,groq,openai
  ENGINE_STOP    := vllm
  ENGINE_START   := sglang
  # vLLM's --gpu-memory-utilization and SGLang's --mem-fraction-static are NOT the
  # same measurement (see docker-compose.gpu.yml), which is why they are separate
  # knobs rather than one number applied to whichever engine is running.
  ENGINE_VLLM_FRAC   := 0.80
  ENGINE_SGLANG_FRAC := 0.55
  ENGINE_CTX         := 8192
  ENGINE_URL_ENV := SGLANG_URL=http://sglang:30000/v1
else ifeq ($(ENGINE),both)
  # BOTH engines resident at once. On a 12GB card this DOES NOT FIT (vLLM 0.80 of
  # FREE + SGLang 0.55 of TOTAL), and the failure is a silent wedge at "Starting to
  # load model", not an error - a CUDA allocator waiting on memory that will never
  # arrive has nothing to report. `up-vllm-sglang` therefore refuses up front rather
  # than letting you discover it after twenty minutes. Intended for a bigger card.
  ENGINE_PROFILE := --profile gpu-vllm --profile gpu-sglang
  ENGINE_CHAIN   := local-vllm,local-sglang,groq,openai
  ENGINE_STOP    :=
  ENGINE_START   := vllm sglang
  # These are the values `both` WOULD need on a card large enough to hold two
  # copies of the weights. On a 12GB card it cannot fit at any fraction - see the
  # arithmetic in up-engine, which refuses before anything loads.
  ENGINE_VLLM_FRAC   := 0.42
  ENGINE_SGLANG_FRAC := 0.42
  # 8k context does not fit beside a second copy of the weights.
  ENGINE_CTX         := 4096
  ENGINE_URL_ENV := VLLM_URL=http://vllm:8000/v1 SGLANG_URL=http://sglang:30000/v1
else ifeq ($(ENGINE),none)
  ENGINE_PROFILE :=
  ENGINE_CHAIN   := groq,openai
  ENGINE_STOP    := vllm sglang
  ENGINE_START   := 
  ENGINE_VLLM_FRAC   := 0.80
  ENGINE_SGLANG_FRAC := 0.55
  ENGINE_CTX         := 8192
  # No local leg, so no URL to export.
  ENGINE_URL_ENV :=
else
  $(error ENGINE must be one of: vllm sglang both none  (got '$(ENGINE)'))
endif

# NO GPU -> NO LOCAL LEG. Applied after the block above so it overrides every
# ENGINE choice, because on a machine with no GPU that choice cannot be honoured.
#
# This is not tidiness. A chain that NAMES a venue which cannot answer costs every
# single request that leg's connect timeout before it fails over - on every request,
# forever - and the breaker only shortens that after it has already paid for three
# failures. Announcing local-sglang on a laptop with no card is a latency bug that
# looks like a configuration comment.
ifneq ($(GPU),1)
  ENGINE_PROFILE :=
  ENGINE_CHAIN   := groq,openai
  ENGINE_STOP    :=
  ENGINE_START   :=
  ENGINE_VLLM_FRAC   := 0.80
  ENGINE_SGLANG_FRAC := 0.55
  ENGINE_CTX         := 8192
  ENGINE_URL_ENV :=
endif

which-engine:   ## Prove which venue actually served the last answer (guessing is not verification)
	@echo ""
	@echo "  ENGINE=$(ENGINE)   SERVING_CHAIN=$(ENGINE_CHAIN)"
	@echo ""
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	for e in vllm:$${VLLM_PORT:-3019} sglang:$${SGLANG_PORT:-3020}; do \
	  name=$${e%%:*}; port=$${e##*:}; \
	  m=$$(curl -s --max-time 5 http://localhost:$$port/v1/models 2>/dev/null \
	       | python -c "import sys,json;print(','.join(x['id'] for x in json.load(sys.stdin)['data']))" 2>/dev/null); \
	  if [ -n "$$m" ]; then printf "  %-8s UP    %s\n" "$$name" "$$m"; \
	  else printf "  %-8s down\n" "$$name"; fi; \
	done
	@echo ""
	@echo "  Both engines serve the SAME model id, so a model name cannot tell them"
	@echo "  apart - ask the API which VENUE answered instead."
	@echo ""


# ==========================================================================================
#  3. vLLM
# ==========================================================================================
#  vLLM only. Nothing in this section touches the data, app or observability tiers.
#
#  `make vllm-up` is the COMPLETE bring-up, in the five stages it actually takes:
#      image (pull if absent) -> weights on disk -> container -> load -> SERVE
#  It waits for SERVING, not for the container to exist. A container that is up and
#  still loading 5.5GB of weights answers nothing, and reporting success there is
#  how a dead engine leg goes unnoticed while a hosted venue quietly bills you.
#
#  FIRST BOOT downloads ~5.5GB and MUST NOT be interrupted: huggingface_hub does not
#  resume across process restarts, so a broken pull starts from byte zero.
# ------------------------------------------------------------------------------------------

vllm-up:        ## vLLM alone: image -> weights -> container -> load -> WAIT until it SERVES
	@nvidia-smi -L >/dev/null 2>&1 || { echo "  No NVIDIA GPU visible to Docker."; exit 1; }
	@bash scripts/engine_preflight.sh vllm || exit 1
	@echo "  checking image..."
	@# NOT an unconditional pull: on a moving :latest tag that silently
	@# re-downloads the whole image (30GB for vllm, 52GB for sglang) and
	@# --quiet hides it. Pull only when the image is genuinely absent.
	@# Force a refresh with:  PULL=1 make up-vllm
	@IMG=$$($(DC_GPU) --profile gpu-vllm config --images 2>/dev/null | head -1); \
	 if [ "$$PULL" = "1" ]; then \
	   echo "  PULL=1: refreshing $$IMG (can be tens of GB)"; \
	   $(DC_GPU) --profile gpu-vllm pull vllm || true; \
	 elif docker image inspect "$$IMG" >/dev/null 2>&1; then \
	   echo "  image present, not pulling: $$IMG"; \
	 else \
	   echo "  image ABSENT, pulling $$IMG (this is the slow one)..."; \
	   $(DC_GPU) --profile gpu-vllm pull vllm || true; \
	 fi
	@# Pre-stage the weights so the DOWNLOAD never happens inside the healthcheck
	@# window. A cold load is ~360s; a cold 5.5GB fetch is ~25min. One timeout
	@# cannot honestly cover both - sized for the load it kills live downloads,
	@# sized for the download it waits 40 minutes on a wedged engine.
	@# Skip with SKIP_WEIGHTS=1 when you know the cache is warm.
	@[ "$$SKIP_WEIGHTS" = "1" ] || bash scripts/ensure_weights.sh || exit 1
	@echo "  starting vllm; waiting for it to SERVE (not merely to start)..."
	@$(DC_GPU) --profile gpu-vllm up -d --wait --wait-timeout $(ENGINE_WAIT) vllm || { \
	  bash scripts/engine_failed.sh vllm $(ENGINE_WAIT); exit 1; }
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 echo "  vllm SERVING on http://localhost:$${VLLM_PORT:-3019}/v1"
	@$(MAKE) --no-print-directory vllm-test

vllm-down:      ## Stop vLLM (weights and image kept)
	@$(DC_GPU) --profile gpu-vllm stop vllm 2>/dev/null || true
	@echo "  vLLM stopped. Weight cache kept."

vllm-upv:       ## Recreate the vLLM container from scratch (weights kept)
	@$(DC_GPU) --profile gpu-vllm rm -sf vllm 2>/dev/null || true
	@$(MAKE) --no-print-directory vllm-up

vllm-downv:     ## Stop vLLM AND delete the SHARED weight cache (costs SGLang its weights too)
	@echo "  WARNING: the weight cache is SHARED with SGLang - this costs BOTH engines"
	@echo "  their weights, and huggingface_hub does not resume across restarts."
	@$(DC_GPU) --profile gpu-vllm rm -sf vllm 2>/dev/null || true
	@P=$$($(PROJECT_CMD)); docker volume rm $${P}_tp_hf_cache 2>/dev/null || true
	@echo "  vLLM removed and weight cache deleted."

vllm-test:      ## How to verify vLLM is really GENERATING (not merely alive)
	@$(MAKE) --no-print-directory engine-guide ENGINE_LABEL=vLLM PORT=$${VLLM_PORT:-3019}


# ==========================================================================================
#  4. SGLANG
# ==========================================================================================
#  SGLang only, mirroring the vLLM section exactly. SGLang is the DEFAULT engine.
#
#  MEMORY IS NOT INTERCHANGEABLE WITH vLLM:
#      vLLM   --gpu-memory-utilization  measures FREE memory and fits inside it
#      SGLang --mem-fraction-static     is a fraction of TOTAL, and ignores whatever
#                                       is already resident
#  On a desktop GPU where the browser and editor hold ~1.2GB, copying vLLM's 0.80
#  here OOM-kills SGLang - and the crash arrives late, after it has been serving
#  happily, the moment someone opens another browser tab.
# ------------------------------------------------------------------------------------------

sglang-up:      ## SGLang alone: image -> weights -> container -> load -> WAIT until it SERVES
	@nvidia-smi -L >/dev/null 2>&1 || { echo "  No NVIDIA GPU visible to Docker."; exit 1; }
	@bash scripts/engine_preflight.sh sglang || exit 1
	@echo "  checking image..."
	@# NOT an unconditional pull: on a moving :latest tag that silently
	@# re-downloads the whole image (30GB for vllm, 52GB for sglang) and
	@# --quiet hides it. Pull only when the image is genuinely absent.
	@# Force a refresh with:  PULL=1 make up-sglang
	@IMG=$$($(DC_GPU) --profile gpu-sglang config --images 2>/dev/null | head -1); \
	 if [ "$$PULL" = "1" ]; then \
	   echo "  PULL=1: refreshing $$IMG (can be tens of GB)"; \
	   $(DC_GPU) --profile gpu-sglang pull sglang || true; \
	 elif docker image inspect "$$IMG" >/dev/null 2>&1; then \
	   echo "  image present, not pulling: $$IMG"; \
	 else \
	   echo "  image ABSENT, pulling $$IMG (this is the slow one)..."; \
	   $(DC_GPU) --profile gpu-sglang pull sglang || true; \
	 fi
	@# Pre-stage the weights so the DOWNLOAD never happens inside the healthcheck
	@# window. A cold load is ~360s; a cold 5.5GB fetch is ~25min. One timeout
	@# cannot honestly cover both - sized for the load it kills live downloads,
	@# sized for the download it waits 40 minutes on a wedged engine.
	@# Skip with SKIP_WEIGHTS=1 when you know the cache is warm.
	@[ "$$SKIP_WEIGHTS" = "1" ] || bash scripts/ensure_weights.sh || exit 1
	@echo "  starting sglang; waiting for it to SERVE (not merely to start)..."
	@$(DC_GPU) --profile gpu-sglang up -d --wait --wait-timeout $(ENGINE_WAIT) sglang || { \
	  bash scripts/engine_failed.sh sglang $(ENGINE_WAIT); exit 1; }
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 echo "  sglang SERVING on http://localhost:$${SGLANG_PORT:-3020}/v1"
	@$(MAKE) --no-print-directory sglang-test

sglang-down:    ## Stop SGLang (weights and image kept)
	@$(DC_GPU) --profile gpu-sglang stop sglang 2>/dev/null || true
	@echo "  SGLang stopped. Weight cache kept."

sglang-upv:     ## Recreate the SGLang container from scratch (weights kept)
	@$(DC_GPU) --profile gpu-sglang rm -sf sglang 2>/dev/null || true
	@$(MAKE) --no-print-directory sglang-up

sglang-downv:   ## Stop SGLang AND delete the SHARED weight cache (costs vLLM its weights too)
	@echo "  WARNING: the weight cache is SHARED with vLLM - this costs BOTH engines"
	@echo "  their weights, and huggingface_hub does not resume across restarts."
	@$(DC_GPU) --profile gpu-sglang rm -sf sglang 2>/dev/null || true
	@P=$$($(PROJECT_CMD)); docker volume rm $${P}_tp_hf_cache 2>/dev/null || true
	@echo "  SGLang removed and weight cache deleted."

sglang-test:    ## How to verify SGLang is really GENERATING (not merely alive)
	@$(MAKE) --no-print-directory engine-guide ENGINE_LABEL=SGLang PORT=$${SGLANG_PORT:-3020}

# ENGINE_LABEL is a DISPLAY name ('vLLM', 'SGLang'), deliberately NOT the ENGINE
# variable: that one is validated against vllm|sglang|none, so passing a capitalised
# label through it would trip the guard and break `make sglang-test`.
engine-guide:
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	MODEL=$${SGLANG_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}; \
	echo ""; \
	echo "  ============================================================"; \
	echo "   $(ENGINE_LABEL) on http://localhost:$(PORT)"; \
	echo "  ============================================================"; \
	echo ""; \
	echo "  -- 1. is it UP? (liveness, NOT capacity) -------------------"; \
	echo "    curl -s localhost:$(PORT)/health"; \
	echo "    curl -s localhost:$(PORT)/v1/models | python -m json.tool"; \
	echo ""; \
	echo "  -- 2. does it actually GENERATE? (the real check) ----------"; \
	echo "    curl -s localhost:$(PORT)/v1/chat/completions -H 'content-type: application/json' -d '{\"model\":\"'$$MODEL'\",\"messages\":[{\"role\":\"user\",\"content\":\"Name three things to do in Kyoto.\"}],\"max_tokens\":80}'"; \
	echo ""; \
	echo "  -- 3. chat with it in a browser ----------------------------"; \
	echo "    make webui   ->  http://localhost:$${OPEN_WEBUI_PORT:-3021}"; \
	echo "    RAW engine: no retrieval, no POI grounding, no itinerary schema."; \
	echo ""; \
	echo "  -- 4. is it on the GPU, and how fast? ----------------------"; \
	echo "    nvidia-smi                 # the process and its VRAM"; \
	echo "    make bench-engine          # TTFT / TPOT / tok-s"; \
	echo ""; \
	echo "  -- 5. is the APP actually using it? ------------------------"; \
	echo "    make which-engine"; \
	echo ""; \
	echo "  Full runbook: docs/gpu-venue.md"; \
	echo ""

webui:          ## Chat straight at the running engine (ChatGPT-style, UNGUARDED path)
	@$(DC_GPU) --profile webui up -d open-webui
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 echo "  Open WebUI  http://localhost:$${OPEN_WEBUI_PORT:-3021}  (no login)"
	@echo "  RAW engine: no retrieval, no citations, no itinerary grounding."
	@echo "  The guarded product UI is the Next.js app - see 'make urls'."

clean-models:   ## DESTRUCTIVE: delete the shared LLM weight cache (~5.5GB)
	@echo "  Deleting tp_hf_cache. It survives 'make downv' deliberately - weights are"
	@echo "  immutable artifacts, not state - so this is the ONLY thing that removes them."
	@echo "  Re-downloading needs ONE uninterrupted run (huggingface_hub cannot resume)."
	@P=$$($(PROJECT_CMD)); docker volume rm $${P}_tp_hf_cache 2>/dev/null || true
	@echo "  Weight cache removed."


# ==========================================================================================
#  5. QUALITY GATES
# ==========================================================================================
#  Lint, types, tests - and `check`, which is exactly what CI runs on every PR.
#
#  Run `make check` before every commit. It is composed from the three targets below
#  rather than repeating their commands, so CI and local can never drift apart.
# ------------------------------------------------------------------------------------------

install:        ## Sync the uv workspace (all packages + dev tools)
	uv sync

lint:           ## Ruff lint
	uv run ruff check .

typecheck:      ## mypy (strict) on package source
	uv run mypy $(MYPY_PATHS)

test:           ## Run the test suite
	uv run pytest

check: lint typecheck test   ## Lint + type-check + test (the green gate)


# ==========================================================================================
#  6. SECURITY & SUPPLY-CHAIN AUDIT
# ==========================================================================================
#  Run `uv sync --group audit` first - these tools live in an optional dependency group
#  so a normal `make install` stays lean.
#
#  `secrets` compares against a REVIEWED baseline (.secrets.baseline) rather than failing
#  on every high-entropy string: the baseline is the record of what a human already looked
#  at and accepted, so only NEW findings break the build.
# ------------------------------------------------------------------------------------------

audit-deps:     ## Supply-chain CVE audit (Python + web prod deps)
	uv run --group audit pip-audit
	pnpm --dir apps/web audit --prod

sast:           ## Static security analysis on first-party source (Bandit)
	uv run --group audit bandit -c pyproject.toml -r packages apps/api apps/worker -q

secrets:        ## Fail on any secret not already in the reviewed baseline
	uv run --group audit detect-secrets-hook --baseline .secrets.baseline $$(git ls-files)

licenses:       ## Print dependency licenses; fail on GPL/AGPL/LGPL/SSPL
	uv run --group audit pip-licenses --fail-on="GPL;AGPL;LGPL;SSPL" --order=license

audit: audit-deps sast licenses   ## Full security/supply-chain audit pass


# ==========================================================================================
#  7. DATA TIER
# ==========================================================================================
#  Postgres, Redis, Qdrant (+ Overpass) - and the jobs that populate them.
#
#  Nothing above this tier starts usefully without it: the worker queries Qdrant on
#  every plan, so an app pointed at an unseeded vector store returns no grounding at all.
#
#  `seed` runs on the HOST, not in a container, and forces VOYAGE_API_KEY empty on
#  purpose: the index must be BUILT with the same embedder the worker QUERIES with.
#  Mixing them puts ingest and query in different vector spaces and RAG silently
#  returns nothing - no error, just empty results.
# ------------------------------------------------------------------------------------------

data:           ## tier 1: DATA stores only - Postgres + Redis + Qdrant
	@$(MAKE) --no-print-directory up-data

services: data  ## Alias for `data` (backwards-compatible name)

seed:           ## Ingest the POI corpus into the running Qdrant server (run after a tier is up)
	set -a; . ./.env 2>/dev/null || true; set +a; \
	QDRANT_URL=http://localhost:$${QDRANT_PORT:-3003} VOYAGE_API_KEY= uv run python -m tp_retrieval.ingest

migrate:        ## Create/upgrade the Postgres schema (idempotent create_all; needs the app tier up)
	# Runs inside the api container: it has the asyncpg driver and the in-network DB URL.
	# (The api also runs this on boot; this target makes the step explicit + re-runnable.)
	$(DC) exec -T api python -c "import asyncio; from tp_core.db import init_models; asyncio.run(init_models())"


# ==========================================================================================
#  8. APP TIER
# ==========================================================================================
#  api, worker, web - containerized, or run natively on the host against the data tier.
#
#  Native dev (`make api` / `make worker`) is the fast inner loop: code reloads without
#  a rebuild, and both processes read .env directly. They still need `make data` first,
#  because the stores are only ever containerized.
# ------------------------------------------------------------------------------------------

app:            ## tier 2: data + APP (api, worker, web)
	@# ONLY the app. --no-deps is the whole point: this must not quietly start
	@# Postgres for you. If the data tier is down, say so instead of crash-looping.
	@$(MAKE) --no-print-directory up-app

api:            ## Run the API with reload on the host (needs `make data`)
	uv run uvicorn tp_api.main:app --reload

worker:         ## Run a Celery worker on the host (needs `make data`)
	uv run celery -A tp_worker.celery_app worker -l info


# ==========================================================================================
#  9. OBSERVABILITY TIER
# ==========================================================================================
#  Jaeger, Prometheus, Grafana, Flower, RedisInsight, Langfuse (+ its own Postgres,
#  ClickHouse and MinIO), Loki, Alertmanager.
#
#  Langfuse state is SPLIT across three stores: its Postgres holds the org/project/keys,
#  ClickHouse the spans, MinIO the raw payloads. That is why all three are wiped together
#  in DATA_VOLS - dropping one alone re-runs the headless bootstrap into a fresh project
#  while the others still hold traces pointing at the old one.
# ------------------------------------------------------------------------------------------

observability:  ## obs only: Jaeger/Grafana/Prometheus/Flower/RedisInsight/Langfuse (standalone)
	@$(MAKE) --no-print-directory up-obs
	@echo ""
	@$(MAKE) --no-print-directory urls


# ==========================================================================================
#  10. LOCAL KUBERNETES (kind)  -  P6.2
# ==========================================================================================
#  A kind cluster + Helm release, parallel to the compose stack rather than replacing it.
#
#  Cluster shape (worker count, node image, replica counts) comes from .env (KIND_*),
#  not hardcoded - see scripts/kind-up.sh, which renders infra/kind/kind-config.yaml
#  with envsubst.
#
#  Resizing an already-running cluster requires `make infra-down` first: kind cannot
#  hot-resize its node count, so changing KIND_WORKER_COUNT on a live cluster silently
#  does nothing.
# ------------------------------------------------------------------------------------------

kind-start:     ## Create the kind cluster if absent, or RESTART its stopped nodes
	@# `make infra` ALONE CANNOT RECOVER A STOPPED CLUSTER. kind still lists a
	@# cluster whose nodes are stopped, so kind-up.sh takes the "already exists"
	@# branch and then runs `kind load` and `helm upgrade` against a dead API
	@# server. Start the node containers first, and always re-export kubeconfig:
	@# a restarted control-plane gets a NEW API port, and the stale config then
	@# fails with "current-context is not set" - which reads like a broken
	@# cluster rather than a stale pointer at a healthy one.
	@if [ "$(KIND)" != "1" ]; then echo "  KIND=0 - skipping kind"; else \
	  set -a; . ./.env 2>/dev/null || true; set +a; \
	  C=$${KIND_CLUSTER_NAME:-voyantra}; \
	   if kind get clusters 2>/dev/null | grep -qx "$$C"; then \
	     echo "  kind: restarting nodes of existing cluster '$$C'"; \
	     docker start $$(kind get nodes --name "$$C" 2>/dev/null) >/dev/null 2>&1 || true; \
	     kind export kubeconfig --name "$$C" >/dev/null 2>&1 || true; \
	     kubectl wait --for=condition=Ready nodes --all --timeout=120s >/dev/null 2>&1 || true; \
	   fi; \
	   bash scripts/kind-up.sh; \
	 fi

kind-stop:      ## Stop the kind nodes, PRESERVING the cluster and everything in it
	@if [ "$(KIND)" != "1" ]; then echo "  KIND=0 - skipping kind"; else \
	  set -a; . ./.env 2>/dev/null || true; set +a; \
	  C=$${KIND_CLUSTER_NAME:-voyantra}; \
	   N=$$(kind get nodes --name "$$C" 2>/dev/null); \
	   if [ -n "$$N" ]; then \
	     docker stop $$N >/dev/null 2>&1 || true; \
	     echo "  kind: nodes of '$$C' stopped - cluster PRESERVED (make downv deletes it)"; \
	   else echo "  kind: no cluster '$$C' - nothing to stop"; fi; \
	 fi

kind-status:    ## Nodes and pods, or a clear reason why there are none
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 C=$${KIND_CLUSTER_NAME:-voyantra}; \
	 if ! kind get clusters 2>/dev/null | grep -qx "$$C"; then \
	   echo "  no kind cluster '$$C' - 'make kind-start' creates one"; \
	 else \
	   kubectl get nodes 2>/dev/null || echo "  nodes unreachable - try 'make kind-start'"; \
	   kubectl get pods 2>/dev/null || true; \
	 fi

kind-down:      ## DESTRUCTIVE: delete the kind cluster (all nodes, etcd, PVCs)
	@if [ "$(KIND)" != "1" ]; then echo "  KIND=0 - skipping kind"; else \
	   bash scripts/kind-down.sh; \
	 fi

# Kept: older docs, scripts and muscle memory call these names.
infra: kind-start          ## Alias for kind-start

infra-down: kind-down      ## Alias for kind-down (DESTRUCTIVE)


# ==========================================================================================
#  11. COMPOSITE LIFECYCLE
# ==========================================================================================
#  full / up / bootstrap / upv / down / downv - COMPOSED from the tier targets above,
#  never from raw compose lines. That is the whole point: change how the data tier starts
#  in section 4 and every one of these follows automatically.
#
#      full        everything in Docker (no kind)      down    stop, ALL data volumes KEPT
#      up          full + the kind/Helm cluster        downv   stop + wipe data (Overpass KEPT)
#      bootstrap   stores + schema + app + corpus      downv-overpass  drop the OSM DB too
#      upv         downv + rebuild + schema + corpus + dashboards
#
#  ORDER IS A DEPENDENCY CHAIN, NOT A PREFERENCE:
#      app      nothing can migrate or seed before the containers exist.
#      migrate  runs `exec -T api`, so it needs that container to EXIST.
#      seed     needs Qdrant reachable; it is what makes retrieval return anything.
#
#  KIND: `up` and `upv` start the cluster; `down` STOPS its nodes and preserves it;
#  `downv` deletes it. Set KIND=0 to ignore Kubernetes entirely. `full` never touches
#  kind at all - that is the whole difference between `full` and `up`.
# ------------------------------------------------------------------------------------------

full:           ## everything in Docker: data + app + observability (no kind/k8s - see 'make up')
	@$(MAKE) --no-print-directory up-data up-app up-obs
	@echo ""
	@$(MAKE) --no-print-directory urls

up:             ## everything: data + app + observability + kind/Helm + the ENGINE named by ENGINE=
	@# ENGINE is the ONE knob (section 1: `ENGINE ?= sglang`). Edit it there, or
	@# override per-invocation: `make up ENGINE=vllm`, `make up ENGINE=none`.
	@# The engine starts BEFORE the app: bring the app up first and its opening
	@# requests hit a venue still loading weights, fail the local leg, trip the
	@# breaker, and get answered by a hosted venue - the silent failover this
	@# whole chain exists to make visible.
	@$(MAKE) --no-print-directory up-engine
	@SERVING_CHAIN=$(ENGINE_CHAIN) $(ENGINE_URL_ENV) $(MAKE) --no-print-directory up-data up-app up-obs
	@if [ "$(KIND)" = "1" ]; then $(MAKE) --no-print-directory kind-start; fi
	@echo ""
	@echo "  ENGINE=$(ENGINE)   SERVING_CHAIN=$(ENGINE_CHAIN)"
	@$(MAKE) --no-print-directory urls

bootstrap:      ## FROM SCRATCH in one shot: stores up + DB schema + app, then seed the corpus
	@$(MAKE) --no-print-directory up-data up-app
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@echo ""
	@echo "  Bootstrap complete - schema created, corpus ingested, app running."
	@echo "  (Run 'make observability' to add the dashboards, or 'make upv' for a clean full setup.)"
	@$(MAKE) --no-print-directory urls

upv:            ## FROM SCRATCH, ONE command: wipe app data, rebuild every tier, schema, corpus, dashboards
	@echo "  make upv - clean rebuild from scratch (wipes app/data volumes; Overpass import kept)."
	@$(MAKE) --no-print-directory downv
	@# ENGINE FIRST, for the same reason `up` does it: bring the app up first and its
	@# opening requests hit a venue still loading weights, fail the local leg, trip the
	@# breaker, and get answered by a hosted venue - the silent failover this chain
	@# exists to make visible. `upv` skipped the engine entirely before this.
	@$(MAKE) --no-print-directory up-engine
	@$(MAKE) --no-print-directory up-data up-app
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory up-obs
	@if [ "$(KIND)" = "1" ]; then $(MAKE) --no-print-directory kind-start; fi
	@echo ""
	@echo "  Up from scratch - all tiers running, schema created, corpus ingested, dashboards up."
	@$(MAKE) --no-print-directory urls

ps:             ## Status of every container in the stack
	$(DC) ps

logs:           ## Tail logs for the whole stack (Ctrl-C to stop)
	$(DC) logs -f --tail=100

down:           ## Stop compose, the ENGINE and the kind nodes. NOTHING is deleted.
	@$(MAKE) --no-print-directory down-compose
	@# The engine is part of the stack, so `down` takes it down too - it used to survive
	@# `make down` and sit there holding ~6.7GB of VRAM while looking like it was gone.
	@# STOP, never rm: the container and its image are kept, so the next `up` reloads
	@# weights from the local cache instead of re-downloading 5.5GB.
	@$(MAKE) --no-print-directory down-engine
	@# STOP, not delete. `down` keeps every compose data volume, so deleting the
	@# cluster here was the one inconsistent thing it did - and it cost a ~2 minute
	@# recreate on the next `up` for no gain: stopping the node containers frees the
	@# same RAM. `make downv` deletes it.
	@if [ "$(KIND)" = "1" ]; then $(MAKE) --no-print-directory kind-stop; fi

downv:          ## Stop the stack AND wipe data volumes, but KEEP the Overpass import
	@$(MAKE) --no-print-directory down-compose
	@# Same as `down`: the engine goes down with the stack, but is only STOPPED.
	@# Model weights and images survive every downv - `make clean-models` is the only
	@# thing that removes weights, and it is deliberately separate.
	@$(MAKE) --no-print-directory down-engine
	@P=$$($(PROJECT_CMD)); \
	  docker volume rm $(foreach v,$(DATA_VOLS),$${P}_$(v)) 2>/dev/null || true; \
	  echo "  Wiped app/data volumes. Overpass DB ($${P}_tp_overpass_db) kept - use 'make downv-overpass' to drop it."
	@# downv is the destructive verb, so this is where the cluster goes. Nothing
	@# in-cluster is persisted outside Helm values and git.
	@if [ "$(KIND)" = "1" ]; then $(MAKE) --no-print-directory kind-down; fi

downv-overpass: ## Wipe ONLY the Overpass OSM database (forces a full re-import on next start)
	-$(DC) rm -f -s -v overpass 2>/dev/null || true
	@P=$$($(PROJECT_CMD)); \
	  docker volume rm $${P}_tp_overpass_db 2>/dev/null || true; \
	  echo "  Overpass DB wiped. Next 'make full' re-imports from OVERPASS_PLANET_FILE (slow)."


# ==========================================================================================
#  TIER PRIMITIVES - the ONLY place a compose verb appears
# ==========================================================================================
#  Every lifecycle target below composes THESE. A target that inlines its own
#  `docker compose` call is a second definition of a tier, and two definitions drift:
#  that is how `make app` ended up starting Postgres while `make data` also did.
# ------------------------------------------------------------------------------------------

up-data:        ## primitive: DATA tier only (db, redis, qdrant, overpass)
	@$(DC) up -d $(SVC_DATA)
	@$(DC) up -d --wait $(SVC_DATA_WAIT)

up-app:         ## primitive: APP tier only (api, worker, web) - starts NO datastore
	@for s in $(SVC_DATA_WAIT); do \
	  if [ -z "$$($(DC) ps -q $$s 2>/dev/null)" ]; then \
	    echo "  '$$s' is not running - the app needs the data tier."; \
	    echo "  Run 'make up-data' first, or 'make full' for every tier."; \
	    exit 1; \
	  fi; \
	done
	@# PREFLIGHT 2: THE CHAIN MUST PARSE. Validated with the REAL parser
	@# (tp_core.llm.venues.parse_chain), so this check can never disagree with what
	@# the app enforces at boot. `SERVING_CHAIN=sglang` is the easy mistake - sglang
	@# is an ENGINE, so it only exists as `local-sglang` - and the ConfigError it
	@# raises reaches you as docker's useless "dependency failed to start".
	@# A BROKEN PREFLIGHT MUST NOT BLOCK THE APP: only a genuine ConfigError
	@# refuses; any other failure warns and continues.
	@OUT=$$(uv run python -c "from tp_core.llm.venues import parse_chain; parse_chain('$(ENGINE_CHAIN)')" 2>&1); \
	 if [ $$? -ne 0 ]; then \
	   if echo "$$OUT" | grep -q ConfigError; then \
	     echo ""; \
	     echo "  REFUSING TO START THE APP TIER: SERVING_CHAIN is not valid."; \
	     echo ""; \
	     echo "      chain: $(ENGINE_CHAIN)"; \
	     echo "$$OUT" | tail -1 | sed 's/^/      /'; \
	     echo ""; \
	     echo "  Entries are 'venue' or 'venue-engine'. vllm and sglang are ENGINES,"; \
	     echo "  valid only as local-vllm / local-sglang, never on their own."; \
	     echo ""; \
	     exit 1; \
	   else echo "  (chain preflight skipped - the parser could not be run)"; fi; \
	 fi
	@# PREFLIGHT 3: AN EMPTY CORPUS IS SILENT. The collection exists, readiness
	@# passes, retrieval returns nothing, and every plan declines with venues=[] -
	@# which is indistinguishable from the app being honest about an unknown city.
	@# WARNS, does NOT refuse: `bootstrap` and `upv` deliberately run up-app BEFORE
	@# seed, so refusing here would break the documented from-scratch path.
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 N=$$(curl -s --max-time 5 "http://localhost:$${QDRANT_PORT:-3003}/collections/pois" 2>/dev/null \
	      | python -c "import sys,json;print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null); \
	 case "$${N:-x}" in \
	   x) echo "  corpus: qdrant not reachable yet - check skipped";; \
	   0) echo ""; \
	      echo "  WARNING: qdrant collection 'pois' is EMPTY."; \
	      echo "           Retrieval will return nothing, so EVERY plan declines with"; \
	      echo "           venues=[] - which looks exactly like honest refusal."; \
	      echo "           Fix with:  make seed"; \
	      echo "";; \
	   *) echo "  corpus: $$N points in 'pois'";; \
	 esac
	@$(DC) up --build -d --no-deps $(SVC_APP)

up-obs:         ## primitive: OBSERVABILITY tier only (14 services)
	@$(DC) up -d $(SVC_OBS)
	@# prometheus.yml is BIND-MOUNTED, so `compose up` sees no container change and
	@# leaves the OLD config loaded. Editing the scrape config and running `make up`
	@# was therefore a SILENT NO-OP. Ask Prometheus to re-read instead.
	@# The result is CHECKED, not assumed: without --web.enable-lifecycle this
	@# endpoint answers 405, and a blind POST would report success on nothing.
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 C=$$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 \
	      -X POST "http://localhost:$${PROMETHEUS_PORT:-3009}/-/reload" 2>/dev/null); \
	 case "$$C" in \
	   200)     echo "  prometheus: scrape config reloaded";; \
	   405)     echo "  prometheus: reload REFUSED (405) - --web.enable-lifecycle missing";; \
	   000|"")  echo "  prometheus: not reachable yet - config reload skipped";; \
	   *)       echo "  prometheus: reload returned HTTP $$C";; \
	 esac
	@$(MAKE) --no-print-directory redisinsight-register

redisinsight-register: ## Register BOTH Redis databases in RedisInsight (idempotent)
	@# Why this is not a nicety: this stack runs TWO Redis instances, and
	@# FLUSHDB on the wrong one is the difference between dropping a few cached
	@# lookups and destroying the Celery queue AND the daily-spend accumulator.
	@# Naming them in the GUI is a safety feature, not decoration.
	@#
	@# It also accepts RedisInsight's agreements, because the ENCRYPTION strategy
	@# is chosen from settings.agreements.encryption and an unset value THROWS -
	@# langfuse-redis uses --requirepass, so without that step its password can
	@# never be stored and it stays missing from the GUI forever.
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 uv run python scripts/redisinsight_register.py || \
	   echo "  RedisInsight: registration skipped (GUI convenience, not fatal)"

down-compose:   ## primitive: stop every compose tier (volumes untouched)
	@$(DC) down

up-engine:      ## Start the engine named by ENGINE= and WAIT until it SERVES
	@# Removes the engine it is NOT using first. `docker compose up` with a different
	@# profile does NOT stop containers outside that profile, so switching
	@# sglang<->vllm would otherwise leave BOTH running and oversubscribe the card.
	@# The trailing "" in each loop keeps an EMPTY list from becoming `for e in ; do`,
	@# which is a shell syntax error, not an empty loop (ENGINE=both stops nothing).
	@# ENGINE=both loads TWO independent copies of the weights. The per-engine
	@# preflight cannot see that: vllm-up passes on its own, loads for ~6 minutes,
	@# and only then does sglang-up refuse - a failure that arrives long after the
	@# decision that caused it. Check the pair BEFORE anything loads.
	@if [ "$(ENGINE)" = "both" ] && [ "$(SKIP_MEM_CHECK)" != "1" ]; then \
	   T=$$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1 | tr -d ' '); \
	   W=$${WEIGHTS_MIB:-5500}; N=$$(( ((W * 14 / 10) + 1500) * 2 )); \
	   if [ -n "$$T" ] && [ "$$T" -lt "$$N" ]; then \
	     echo ""; \
	     echo "  REFUSING ENGINE=both: this card cannot hold two engines."; \
	     echo ""; \
	     echo "      card total   $$T MiB"; \
	     echo "      needed      ~$$N MiB   (2 x ($$W weights x1.4 + 1500 runtime))"; \
	     echo ""; \
	     echo "  Each engine loads its OWN copy of the weights, so this is not a"; \
	     echo "  fraction to tune - it is more memory than the card has. Lowering"; \
	     echo "  ENGINE_VLLM_FRAC/ENGINE_SGLANG_FRAC cannot fix it."; \
	     echo ""; \
	     echo "  Use one engine:   make up ENGINE=sglang     (or ENGINE=vllm)"; \
	     echo "  Hosted only:      make up ENGINE=none"; \
	     echo "  Override anyway:  make up ENGINE=both SKIP_MEM_CHECK=1"; \
	     echo ""; \
	     exit 1; \
	   fi; \
	 fi
	@if [ -z "$(ENGINE_PROFILE)" ]; then \
	  echo "  ENGINE=none - hosted chain only ($(ENGINE_CHAIN))"; \
	else \
	  for e in $(ENGINE_STOP) ""; do \
	    [ -n "$$e" ] || continue; \
	    $(DC_GPU) $(ALL_ENGINE_PROFILES) rm -sf $$e >/dev/null 2>&1 || true; \
	  done; \
	  for e in $(ENGINE_START) ""; do \
	    [ -n "$$e" ] || continue; \
	    VLLM_GPU_MEMORY_UTILIZATION=$(ENGINE_VLLM_FRAC) \
	    SGLANG_MEM_FRACTION=$(ENGINE_SGLANG_FRAC) \
	    VLLM_MAX_MODEL_LEN=$(ENGINE_CTX) SGLANG_MAX_MODEL_LEN=$(ENGINE_CTX) \
	    $(MAKE) --no-print-directory $$e-up || exit 1; \
	  done; \
	fi

down-engine:    ## Stop EVERY engine, whichever one is currently selected
	@$(DC_GPU) $(ALL_ENGINE_PROFILES) stop >/dev/null 2>&1 || true
	@echo "  engines stopped (weights and images kept)"

up-vllm:        ## Whole app served by vLLM    (SERVING_CHAIN=local-vllm,groq,openai)
	@$(MAKE) --no-print-directory up-with-engine ENGINE=vllm

up-sglang:      ## Whole app served by SGLang  (SERVING_CHAIN=local-sglang,groq,openai)
	@$(MAKE) --no-print-directory up-with-engine ENGINE=sglang

up-vllm-sglang: ## Whole app on BOTH engines   (SERVING_CHAIN=local-vllm,local-sglang,groq,openai)
	@# Refuse on a card that cannot hold two 7B models rather than wedging. Two
	@# engines are NOT independent failure domains anyway - both die with the GPU -
	@# so this buys protection against an engine fault only, never a hardware one.
	@tot=$$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits 2>/dev/null | head -1); 	 if [ -z "$$tot" ]; then echo "  No NVIDIA GPU visible to Docker."; exit 1; fi; 	 if [ "$$tot" -lt 24000 ] && [ "$$SKIP_MEM_CHECK" != "1" ]; then 	   echo ""; 	   echo "  REFUSING: both engines need ~2x7B resident; this card has $${tot} MiB."; 	   echo "  Two 7B models at INT4 + KV cache need ~24000 MiB to be safe."; 	   echo ""; 	   echo "  It would not fail fast - vLLM WEDGES at 'Starting to load model' with"; 	   echo "  no error line, because a CUDA allocator waiting on memory that never"; 	   echo "  arrives has nothing to report."; 	   echo ""; 	   echo "  Use one at a time:   make up-sglang   |   make up-vllm"; 	   echo "  Override anyway:     make up-vllm-sglang SKIP_MEM_CHECK=1"; 	   echo ""; 	   exit 1; 	 fi
	@$(MAKE) --no-print-directory up-with-engine ENGINE=both

# SERVING_CHAIN *and* the engine URL are EXPORTED here, not left to .env. Shell env
# beats env_file for compose interpolation, and that is the only thing that makes
# ENGINE= authoritative. Without it this target PRINTS one chain while the container
# RUNS another - a knob that reports a value it does not apply is worse than no knob,
# because it is believed.
#
# Exporting the chain is NOT enough on its own: docker-compose.app.yml must also name
# these vars under `environment:`, because it uses an explicit allowlist rather than
# env_file. A var absent from that list reaches no container no matter who exports it.
#
# ORDER MATTERS. The engine comes up BEFORE the app. Start the app first and it points
# at a venue still loading ~5.5GB of weights, so its opening requests fail the local
# leg, trip the breaker, and get answered - and BILLED - by a hosted venue, which is
# the exact silent-failover this whole chain exists to make visible.
up-with-engine:
	@$(MAKE) --no-print-directory data
	@$(MAKE) --no-print-directory up-engine
	@SERVING_CHAIN=$(ENGINE_CHAIN) $(ENGINE_URL_ENV) $(MAKE) --no-print-directory up-data up-app
	@echo ""
	@echo "  ENGINE=$(ENGINE)   SERVING_CHAIN=$(ENGINE_CHAIN)   $(ENGINE_URL_ENV)"
	@$(MAKE) --no-print-directory urls


# ==========================================================================================
#  12. EVAL, LOAD & CHAOS
# ==========================================================================================
#  The harnesses that answer "is it still correct" and "does it hold up".
#
#  `eval` runs against fixtures and makes real LLM calls, so it costs real (small) money -
#  it needs OPENAI_API_KEY. `eval-rag` additionally goes through real retrieval, so the
#  corpus must already be ingested: run `make ingest` (native) or `make seed` (server) first.
#
#  `chaos` kills dependencies (LLM, Redis, Qdrant) and asserts the system DEGRADES rather
#  than fails - the D21 contract. It never deletes a volume.
# ------------------------------------------------------------------------------------------

bench-engine:   ## Measure the LOCAL engine named by ENGINE= (TTFT / TPOT / tok-s)
	@if [ "$(ENGINE)" = "none" ]; then echo "  ENGINE=none - no local engine to benchmark."; exit 1; fi
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	if [ "$(ENGINE)" = "vllm" ]; then P=$${VLLM_PORT:-3019}; M=$${VLLM_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}; \
	else P=$${SGLANG_PORT:-3020}; M=$${SGLANG_MODEL:-Qwen/Qwen2.5-7B-Instruct-AWQ}; fi; \
	uv run python scripts/bench_venue.py --label local-$(ENGINE) \
	  --base-url http://localhost:$$P/v1 --model "$$M"

bench-groq:     ## Measure the Groq leg with the SAME harness (needs GROQ_API_KEY)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	uv run python scripts/bench_venue.py --label groq \
	  --base-url https://api.groq.com/openai/v1 \
	  --model $${GROQ_BENCH_MODEL:-qwen/qwen3.8-27b} --api-key "$$GROQ_API_KEY"

bench-openai:   ## Measure the OpenAI leg with the SAME harness (COSTS MONEY)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	uv run python scripts/bench_venue.py --label openai \
	  --base-url https://api.openai.com/v1 \
	  --model $${OPENAI_BENCH_MODEL:-gpt-4o-mini} --api-key "$$OPENAI_API_KEY"

ingest:         ## Ingest the seed POI corpus into Qdrant (needs OPENAI_API_KEY for embeddings)
	uv run python -m tp_retrieval.ingest

eval:           ## Run the eval harness on fixtures (needs OPENAI_API_KEY; LLM calls cost ~cents)
	uv run python -m tp_eval --judge gateway

eval-rag:       ## Run eval through real retrieval (run `make ingest` first)
	uv run python -m tp_eval --judge gateway --retrieve

load:           ## k6 load test against $(BASE_URL) (default http://localhost:8000)
	BASE_URL=$(BASE_URL) k6 run tests/load/plan_smoke.js

chaos:          ## Resilience/chaos tests (kill LLM / Redis / Qdrant, assert graceful degradation)
	uv run pytest -m chaos -v



# ==========================================================================================
#  12b. TESTING HELPERS - cache + history
# ==========================================================================================
#  Re-running the same query during testing is only "fresh" if you know what is reused.
#
#  WHAT THE CACHE ACTUALLY DOES HERE: there is NO response cache. Four TOOL caches exist
#  (geo, pois, wx, route). A repeated query still creates a new run and still calls the
#  LLM - measured: two run ids, two completions, only the geocode and weather lookups
#  reused. So clearing the cache changes external lookups, and never changes whether the
#  model runs or what it costs.
#
#  WHY THE PREFIX IS ASKED FOR, NOT WRITTEN DOWN: keys are namespaced by
#  `{PROMPT_VERSION}.{CORPUS_VERSION}.{INDEX_VERSION}`, computed at runtime. A literal
#  `v1.v1.v1` here would go stale the moment anyone bumped a version and would then
#  silently clear nothing while appearing to work.
#
#  WHY NOT FLUSHDB: this Redis is also the Celery broker AND result backend AND the
#  daily-spend accumulator. Flushing it destroys the task queue and the cost control.
#  Every target below is scoped to the cache prefix and touches nothing else.
# ------------------------------------------------------------------------------------------

cache-prefix:   ## Print the cache key prefix the RUNNING app computes
	@$(DC) exec -T worker python -c "from tp_core.cache import cache_version; print(cache_version())" 2>/dev/null | tr -d "\r"

cache-ls:       ## List cached tool lookups (geo/pois/wx/route) under the current prefix
	@P=$$($(MAKE) -s cache-prefix); \
	 if [ -z "$$P" ]; then echo "  worker not running - start it with 'make up-app'"; exit 1; fi; \
	 echo "  prefix: $$P"; \
	 N=$$($(DC) exec -T redis redis-cli --scan --pattern "$$P:*" 2>/dev/null | grep -c . || true); \
	 $(DC) exec -T redis redis-cli --scan --pattern "$$P:*" 2>/dev/null | sed "s/^/    /"; \
	 echo "  $$N cached lookup(s)"; \
	 echo ""; \
	 echo "  NOT cache, and deliberately left alone by cache-clear:"; \
	 echo "    spend:usd:*            the daily spend breaker"; \
	 echo "    celery-task-meta-*     Celery result backend"; \
	 echo "    _kombu.binding.*       Celery broker"; \
	 echo "    ratelimit:*            rate-limit windows"

cache-clear:    ## Drop cached tool lookups so the next query re-fetches them
	@# Scoped to the cache prefix ONLY. Celery state, the spend accumulator and the
	@# rate-limit windows all survive - flushing them would break the app you are testing.
	@P=$$($(MAKE) -s cache-prefix); \
	 if [ -z "$$P" ]; then echo "  worker not running - start it with 'make up-app'"; exit 1; fi; \
	 KEYS=$$($(DC) exec -T redis redis-cli --scan --pattern "$$P:*" 2>/dev/null | tr -d "\r" | grep -c . || true); \
	 if [ "$$KEYS" = "0" ]; then echo "  nothing cached under $$P"; else \
	   $(DC) exec -T redis sh -c "redis-cli --scan --pattern '$$P:*' | xargs -r redis-cli del" >/dev/null 2>&1; \
	   echo "  cleared $$KEYS cached lookup(s) under $$P"; \
	 fi; \
	 echo "  kept: spend, celery, rate-limit counters"

state-ls:       ## Show what persistent state exists (rows per table) before deleting any
	@$(DC) exec -T db psql -U "$${POSTGRES_USER:-tp}" -d "$${POSTGRES_DB:-tp}" -tAc \
	  "select 'runs', count(*) from runs \
	    union all select 'checkpoints', count(*) from checkpoints \
	    union all select 'checkpoint_writes', count(*) from checkpoint_writes \
	    union all select 'checkpoint_blobs', count(*) from checkpoint_blobs;" \
	  2>/dev/null | tr -d "\r" | awk -F'|' '{printf "    %-20s %s rows\n", $$1, $$2}'
	@echo ""
	@echo "  checkpoints are LangGraph state, keyed by thread_id = the run_id."
	@echo "  Every run is its own thread, so they NEVER make a repeated query stale;"
	@echo "  they are history and disk, not cache. 'make cache-clear' is what makes"
	@echo "  a repeat query fresh."

runs-clear:     ## DESTRUCTIVE: delete run history + LangGraph checkpoints from Postgres
	@# Separate from cache-clear on purpose. The cache is a performance detail; run
	@# history is the system of record, and deleting it silently alongside a cache drop
	@# would be a surprise nobody asked for.
	@# The checkpoint tables go WITH the runs: thread_id is the run_id, so a checkpoint
	@# whose run is gone is unreachable garbage. checkpoint_migrations is NOT touched --
	@# that is schema bookkeeping, not run state.
	@printf "  Delete ALL run history AND checkpoints? this cannot be undone [y/N] "; read a; \
	 case "$$a" in [yY]*) \
	   $(DC) exec -T db psql -U "$${POSTGRES_USER:-tp}" -d "$${POSTGRES_DB:-tp}" \
	     -c "truncate table runs, checkpoints, checkpoint_writes, checkpoint_blobs;" \
	     && echo "  run history and checkpoints cleared";; \
	   *) echo "  cancelled";; \
	 esac

metrics-note:   ## Why you cannot "reset" Prometheus counters
	@echo ""
	@echo "  Prometheus counters CANNOT be reset in place, and nothing here pretends to."
	@echo "  They are process-lifetime totals: the only reset is restarting the process"
	@echo "  that exports them, which zeroes tp_* on that endpoint."
	@echo ""
	@echo "    make up-app          restarts api + worker  -> both counter sets reset"
	@echo ""
	@echo "  This is why the venue rows on the dashboard say 'not served since restart'"
	@echo "  rather than 'no data': since-restart is the honest window, not a defect."
	@echo "  rate() handles the reset correctly; cumulative panels simply start again."
	@echo ""

# ==========================================================================================
#  13. SERVICE DIRECTORY
# ==========================================================================================
#  One place that answers "which URL opens which UI".
#
#  Ports are read from .env at RUN TIME (with the same defaults the compose files use),
#  so this listing cannot drift from what is actually published. They are sequenced by
#  STARTUP ORDER - data 3001-3003, app 3004-3006, observability 3007-3018 - which makes
#  a port number tell you which tier it belongs to.
# ------------------------------------------------------------------------------------------

# ==========================================================================================
#  12c. RUNTIME SWITCHES, VERIFICATION, INFRA-AS-CODE, IMAGES
# ==========================================================================================
#  Things the application already supports but had no command for.
#
#  The kill switch is the clearest example: `planning:enabled` has worked since the
#  control layer was written and the inspection scripts assert it returns 503 - but
#  flipping it meant hand-typing a redis-cli line against the right container, which
#  is exactly how people end up setting a key that nothing reads.
# ------------------------------------------------------------------------------------------

kill-on:        ## Kill switch ON = planning DISABLED (POST /plan answers 503)
	@$(DC) exec -T redis redis-cli set planning:enabled 0 >/dev/null
	@echo "  Planning DISABLED. POST /plan answers 503 and NO venue is contacted."

kill-off:       ## Kill switch OFF = planning ENABLED (the normal state)
	@$(DC) exec -T redis redis-cli del planning:enabled >/dev/null
	@echo "  Planning ENABLED."
	@# The switch is one-directional by design: it can only ever DISABLE.
	@echo "  NOTE: LLM_ENABLED=false in .env is a FLOOR - no Redis value can lift it."

kill-status:    ## Is planning currently enabled, and what is the floor?
	@# REACHABILITY FIRST. Without this, a stack that is simply DOWN reads as
	@# 'ENABLED - no runtime override set': the exec fails, stderr is discarded, and
	@# the empty result lands in the same branch as 'no key set'. Absent and
	@# unreachable are different answers, and this is the one command you have to be
	@# able to trust during an incident.
	@$(DC) exec -T redis redis-cli ping >/dev/null 2>&1 || { \
	   echo "  UNKNOWN - redis is not reachable, so the switch cannot be read."; \
	   echo "  Start the data tier first:  make up-data"; \
	   exit 1; }
	@V=$$($(DC) exec -T redis redis-cli get planning:enabled 2>/dev/null | tr -d "\r"); \
	 case "$$V" in \
	   0|false) echo "  DISABLED - runtime kill switch is set (planning:enabled=$$V)";; \
	   "")      echo "  ENABLED  - no runtime override set";; \
	   *)       echo "  ENABLED  - planning:enabled=$$V (only 0 and false disable)";; \
	 esac
	@F=$$(grep -E '^LLM_ENABLED=' .env 2>/dev/null | cut -d= -f2); \
	 echo "  floor: LLM_ENABLED=$${F:-(unset, defaults true)}"

inspect:        ## BRUTAL end-to-end inspection of the chain for ENGINE= (sglang|vllm)
	@# The full battery: containers, datastores, celery, prometheus targets, env
	@# hygiene, embedder stamp, kill switch, spend growth, honest degradation, the
	@# whole failover ladder, every dashboard panel, and both Jaeger services.
	@case "$(ENGINE)" in \
	   sglang|vllm) uv run python scripts/inspect_stack_$(ENGINE).py;; \
	   *) echo "  ENGINE=$(ENGINE) has no inspection script (only sglang and vllm do)."; \
	      echo "  Use: make inspect ENGINE=sglang   or   make inspect ENGINE=vllm"; \
	      exit 1;; \
	 esac

inspect-sglang: ## Inspect the local-sglang -> groq -> openai chain
	@$(MAKE) --no-print-directory inspect ENGINE=sglang

inspect-vllm:   ## Inspect the local-vllm -> groq -> openai chain
	@$(MAKE) --no-print-directory inspect ENGINE=vllm

smoke:          ## Two plans: one in-corpus (must GROUND) and one that must DECLINE
	@# Dispatch and polling are imported from the inspection module, so this can
	@# never drift from how the real battery submits a run.
	@uv run python scripts/smoke.py

weights-status: ## What engine weights are on disk (READ-ONLY - never downloads)
	@# Deliberately NOT `ensure_weights.sh`: that script DOWNLOADS when the cache is
	@# incomplete, and a target called 'status' must never start a 5.5GB transfer.
	@P=$$($(PROJECT_CMD)); V=$${P}_tp_hf_cache; \
	 if ! docker volume inspect "$$V" >/dev/null 2>&1; then \
	   echo "  no weight volume '$$V' - 'make weights-ensure' creates it"; \
	 else \
	   echo "  volume: $$V"; \
	   docker run --rm -v "$$V":/c alpine sh -c \
	     "du -sh /c 2>/dev/null | sed 's|/c|  on disk|'; \
	      find /c -name '*.incomplete' 2>/dev/null | sed 's|^|  INCOMPLETE: |'" \
	     2>/dev/null || echo "  (could not read the volume)"; \
	 fi

weights-ensure: ## Make engine weights present and complete (RESUMABLE; may fetch ~5.5GB)
	@# huggingface_hub does NOT resume across processes, so an interrupted fetch
	@# restarts from byte zero. Let this finish.
	@set -a; . ./.env 2>/dev/null || true; set +a; bash scripts/ensure_weights.sh

gpu:            ## Start ONLY the engine named by ENGINE= (no app, no data, no obs)
	@# NOT 'start both engines'. On a 12GB card the two together are configured for
	@# 0.80 + 0.55 = 135% of the card; a target that quietly launched both would be
	@# handing you an OOM. ENGINE=both is the explicit, eyes-open way to ask for it.
	@$(MAKE) --no-print-directory up-engine

gpu-down:       ## Stop every engine (weights and images kept)
	@$(MAKE) --no-print-directory down-engine

cache-flush:    ## DESTRUCTIVE: wipe ALL of Redis - queue, results, spend, rate limits
	@# This is NOT 'make cache-clear'. That one is scoped to the cache prefix.
	@echo "  Redis here is ALSO the Celery broker, the result backend, the daily-spend"
	@echo "  accumulator and the rate-limit store. Flushing destroys in-flight tasks and"
	@echo "  the cost control, not just cached lookups. 'make cache-clear' is scoped."
	@printf "  Wipe the ENTIRE Redis db? [y/N] "; read a; \
	 case "$$a" in \
	   [yY]*) $(DC) exec -T redis redis-cli flushdb >/dev/null && echo "  Redis db flushed.";; \
	   *) echo "  cancelled";; \
	 esac

tf-init:        ## terraform init (providers only; no backend, no credentials needed)
	terraform -chdir=infra/terraform init -backend=false -input=false

tf-validate:    ## terraform fmt -check + validate - proves the HCL is correct OFFLINE
	terraform -chdir=infra/terraform fmt -check -recursive
	terraform -chdir=infra/terraform validate

tf-plan:        ## terraform plan - NEEDS AWS credentials. Never applies anything.
	terraform -chdir=infra/terraform plan -input=false

chart-lint:     ## helm lint + a census of the objects the chart actually renders
	helm lint infra/helm/voyantra -f infra/helm/voyantra/values-kind.yaml
	@helm template voyantra infra/helm/voyantra -f infra/helm/voyantra/values-kind.yaml \
	   --set secrets.openaiApiKey=test 2>/dev/null \
	   | grep '^kind:' | sort | uniq -c

images:         ## Build the three service images that kind side-loads
	docker build -t tp-api:$(IMAGE_TAG)    -f apps/api/Dockerfile    .
	docker build -t tp-worker:$(IMAGE_TAG) -f apps/worker/Dockerfile .
	docker build -t tp-web:$(IMAGE_TAG)    -f apps/web/Dockerfile    ./apps/web
	@docker images --filter=reference='tp-*'

clean-images:   ## DESTRUCTIVE: remove THIS project's built images. Weights kept.
	-docker rmi tp-api:$(IMAGE_TAG) tp-worker:$(IMAGE_TAG) tp-web:$(IMAGE_TAG) 2>/dev/null
	@# The vllm/sglang images are deliberately NOT touched. They are upstream images
	@# shared with other work on this machine, and removing them would cost an
	@# unrelated project an ~83GB re-pull. Remove those by hand if you truly mean to.
	@echo "  Rebuild with 'make images'. Engine images and model weights untouched."

clean-all: clean-images clean-models   ## DESTRUCTIVE: built images AND model weights
	@echo "  Next 'make up' is a cold build: images rebuild and weights re-download."

langfuse:       ## Open Langfuse and print the ONE login it needs
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 echo ""; \
	 echo "  Langfuse   http://localhost:$${LANGFUSE_PORT:-3013}"; \
	 echo ""; \
	 echo "  Sign in ONCE - Langfuse has no anonymous viewer mode the way Grafana"; \
	 echo "  does, so this is the one dashboard that cannot be made login-free."; \
	 echo ""; \
	 echo "    email     $${LANGFUSE_INIT_USER_EMAIL:-(see .env)}"; \
	 echo "    password  $${LANGFUSE_INIT_USER_PASSWORD:-(see .env)}"; \
	 echo ""; \
	 echo "  You do NOT create a project or copy API keys: the org, project and both"; \
	 echo "  keys are bootstrapped from .env on first boot. Traces are there already."

service_ls:     ## Inventory WITH local dev credentials (never prints provider API keys)
	@# 'make urls' is the credential-free version. This one adds logins and
	@# connection strings for LOCAL services only. OPENAI_API_KEY, GROQ_API_KEY and
	@# every other provider secret are deliberately NOT printed: a target that echoes
	@# real keys into a terminal, a screen share or a scrollback is a liability.
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	 echo ""; \
	 echo "  Voyantra - local services WITH dev credentials"; \
	 echo "  ------------------------------------------------------------------"; \
	 echo "  Postgres    postgresql://$${POSTGRES_USER:-tp}:$${POSTGRES_PASSWORD:-tp}@localhost:$${POSTGRES_PORT:-3001}/$${POSTGRES_DB:-tp}"; \
	 echo "  Redis       redis://localhost:$${REDIS_PORT:-3002}/0   (no auth in dev)"; \
	 echo "  Qdrant      http://localhost:$${QDRANT_PORT:-3003}/dashboard   (no auth in dev)"; \
	 echo "  Web app     http://localhost:$${WEB_PORT:-3006}   login: $${DEV_LOGIN_PASSWORD:-voyantra}"; \
	 echo "  Grafana     http://localhost:$${GRAFANA_PORT:-3010}   anonymous admin, no login"; \
	 echo "  Langfuse    http://localhost:$${LANGFUSE_PORT:-3013}   $${LANGFUSE_INIT_USER_EMAIL:-(see .env)}"; \
	 echo ""; \
	 echo "  chain       $${SERVING_CHAIN:-(unset)}"; \
	 echo "  provider keys: NOT printed by design - grep .env yourself if you need one."; \
	 echo ""

urls:           ## Print which URL opens which UI (ports come from .env)
	@set -a; . ./.env 2>/dev/null || true; set +a; \
	echo ""; \
	echo "  Voyantra - local URLs   (ports are sequenced by startup order in .env)"; \
	echo "  ---------------------------------------------------------------------"; \
	echo "  -- data tier (starts 1st) ----"; \
	echo "  Postgres             localhost:$${POSTGRES_PORT:-3001}            (DB client; user/pass=$${POSTGRES_USER:-tp})"; \
	echo "  Redis                localhost:$${REDIS_PORT:-3002}            (RedisInsight or redis-cli)"; \
	echo "  Qdrant dashboard     http://localhost:$${QDRANT_PORT:-3003}/dashboard"; \
	echo "  Overpass (POIs)      http://localhost:$${OVERPASS_PORT:-3015}/api/status            (first start imports the OSM extract, ~2-4h)"; \
	echo "  -- app tier (starts 2nd) ----"; \
	echo "  API docs (Swagger)   http://localhost:$${API_PORT:-3004}/docs"; \
	echo "  API metrics (raw)    http://localhost:$${API_PORT:-3004}/metrics"; \
	echo "  App (Next.js)        http://localhost:$${WEB_PORT:-3006}            login: $${DEV_LOGIN_PASSWORD:-voyantra}"; \
	echo "  -- observability tier (starts 3rd) ----"; \
	echo "  Jaeger  (traces)     http://localhost:$${JAEGER_UI_PORT:-3007}            service: tp-worker"; \
	echo "  Prometheus           http://localhost:$${PROMETHEUS_PORT:-3009}            Status > Targets"; \
	echo "  Grafana (metrics)    http://localhost:$${GRAFANA_PORT:-3010}            anonymous admin"; \
	echo "  Flower  (Celery)     http://localhost:$${FLOWER_PORT:-3011}"; \
	echo "  RedisInsight         http://localhost:$${REDISINSIGHT_PORT:-3012}            add host=redis port=6379"; \
	echo "  Langfuse (LLM trace) http://localhost:$${LANGFUSE_PORT:-3013}            (make observability or make full)"; \
	echo "  MinIO console        http://localhost:$${MINIO_CONSOLE_PORT:-3014}"; \
	echo "  Loki (logs)          http://localhost:$${LOKI_PORT:-3100}            query in Grafana > Explore > Loki"; \
	echo "  Alertmanager         http://localhost:$${ALERTMANAGER_PORT:-9093}"; \
	echo "  ---------------------------------------------------------------------"; \
	echo ""
