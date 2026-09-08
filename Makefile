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

.PHONY: api app audit cache-clear cache-ls cache-prefix metrics-note runs-clear down-compose up-app up-data up-obs audit-deps bench-engine bench-groq bench-openai bootstrap chaos check clean-models data down down-engine downv downv-overpass engine-guide eval eval-rag full help infra infra-down ingest install licenses lint load logs migrate observability ps sast secrets seed services sglang-down sglang-downv sglang-test sglang-up sglang-upv test typecheck up up-engine up-sglang up-vllm up-vllm-sglang up-with-engine upv urls vllm-down vllm-downv vllm-test vllm-up vllm-upv webui which-engine worker state-ls

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
  # In-network URL: the gpu tier shares THIS compose project, so the service name
  # resolves with no host port. Exported by up-with-engine so ENGINE= is authoritative.
  ENGINE_URL_ENV := VLLM_URL=http://vllm:8000/v1
else ifeq ($(ENGINE),sglang)
  ENGINE_PROFILE := --profile gpu-sglang
  ENGINE_CHAIN   := local-sglang,groq,openai
  ENGINE_STOP    := vllm
  ENGINE_START   := sglang
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
  ENGINE_URL_ENV := VLLM_URL=http://vllm:8000/v1 SGLANG_URL=http://sglang:30000/v1
else ifeq ($(ENGINE),none)
  ENGINE_PROFILE :=
  ENGINE_CHAIN   := groq,openai
  ENGINE_STOP    := vllm sglang
  ENGINE_START   := 
  # No local leg, so no URL to export.
  ENGINE_URL_ENV :=
else
  $(error ENGINE must be one of: vllm sglang both none  (got '$(ENGINE)'))
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

infra:          ## Bring up the local kind cluster + Helm-deployed app (reads KIND_* from .env)
	bash scripts/kind-up.sh

infra-down:     ## DESTRUCTIVE: delete the entire kind cluster (all nodes, etcd, PVCs)
	bash scripts/kind-down.sh


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
#  `down` also deletes the kind cluster: nothing in-cluster is persisted, so keeping a
#  half-stopped cluster around only wastes RAM. Compose data volumes ARE kept.
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
	@$(MAKE) --no-print-directory infra
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
	@$(MAKE) --no-print-directory up-data up-app
	@$(MAKE) --no-print-directory migrate
	@$(MAKE) --no-print-directory seed
	@$(MAKE) --no-print-directory up-obs
	@echo ""
	@echo "  Up from scratch - all tiers running, schema created, corpus ingested, dashboards up."
	@$(MAKE) --no-print-directory urls

ps:             ## Status of every container in the stack
	$(DC) ps

logs:           ## Tail logs for the whole stack (Ctrl-C to stop)
	$(DC) logs -f --tail=100

down:           ## Stop compose (keeps ALL data volumes) AND delete the kind cluster
	@$(MAKE) --no-print-directory down-compose
	@echo ""
	@echo "  Also deleting the kind cluster (all nodes + in-cluster state) - this is NOT kept:"
	@$(MAKE) --no-print-directory infra-down

downv:          ## Stop the stack AND wipe data volumes, but KEEP the Overpass import
	@$(MAKE) --no-print-directory down-compose
	@P=$$($(PROJECT_CMD)); \
	  docker volume rm $(foreach v,$(DATA_VOLS),$${P}_$(v)) 2>/dev/null || true; \
	  echo "  Wiped app/data volumes. Overpass DB ($${P}_tp_overpass_db) kept - use 'make downv-overpass' to drop it."

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
	@$(DC) up --build -d --no-deps $(SVC_APP)

up-obs:         ## primitive: OBSERVABILITY tier only (14 services)
	@$(DC) up -d $(SVC_OBS)

down-compose:   ## primitive: stop every compose tier (volumes untouched)
	@$(DC) down

up-engine:      ## Start the engine named by ENGINE= and WAIT until it SERVES
	@# Removes the engine it is NOT using first. `docker compose up` with a different
	@# profile does NOT stop containers outside that profile, so switching
	@# sglang<->vllm would otherwise leave BOTH running and oversubscribe the card.
	@# The trailing "" in each loop keeps an EMPTY list from becoming `for e in ; do`,
	@# which is a shell syntax error, not an empty loop (ENGINE=both stops nothing).
	@if [ -z "$(ENGINE_PROFILE)" ]; then \
	  echo "  ENGINE=none - hosted chain only ($(ENGINE_CHAIN))"; \
	else \
	  for e in $(ENGINE_STOP) ""; do \
	    [ -n "$$e" ] || continue; \
	    $(DC_GPU) $(ALL_ENGINE_PROFILES) rm -sf $$e >/dev/null 2>&1 || true; \
	  done; \
	  for e in $(ENGINE_START) ""; do \
	    [ -n "$$e" ] || continue; \
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
