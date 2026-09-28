#!/usr/bin/env bash
# Apply the WORKFLOW_*_ENABLED flags in .env to the three GitHub Actions workflows.
#
# WHY A SCRIPT, AND NOT .env ALONE
# --------------------------------
# GitHub never reads .env: it is gitignored, so a push does not carry it. The three
# flags therefore do NOTHING until this script applies them with
# `gh workflow enable|disable`, which flips each workflow's state on GitHub itself.
#
# WHY `gh workflow disable`, AND NOT A JOB-LEVEL `if: vars.X == 'true'`
# ---------------------------------------------------------------------
# A DISABLED workflow does not start: no run, no red X, no failure email. A job-level
# `if:` still creates a run on every push and marks it skipped - and switching it on
# means committing and PUSHING the edited YAML, where the push is the very event that
# triggers the failing runs. This takes effect the moment it runs; nothing to commit.
#
# SAFE DEFAULTS
# -------------
# Unset or empty counts as ENABLED, so a missing flag can never silently switch CI
# off. A value that is not plainly true/false is REFUSED, not guessed - and one bad
# value refuses the whole run, so the three workflows never end up half-applied.
#
# IDEMPOTENT
# ----------
# `gh workflow disable` fails on a workflow that is already disabled (it searches only
# active ones) and `enable` the reverse. So the live state is read FIRST and only the
# workflows that actually need to change are touched.
#
# PRECEDENCE
# ----------
# A flag already set in the environment beats .env, so a one-off works without
# editing the file:   make gh-workflows WORKFLOW_CD_ENABLED=true
#
# Usage:  bash scripts/gh_workflows.sh              apply .env to GitHub
#         DRY_RUN=1 bash scripts/gh_workflows.sh    the plan only - calls nothing
#         bash scripts/gh_workflows.sh --status     GitHub's live state vs .env
set -euo pipefail

WORKFLOWS="ci cd promote"

# -- read the flags: environment first, then .env ------------------------------------
_ci="${WORKFLOW_CI_ENABLED-}"; _cd="${WORKFLOW_CD_ENABLED-}"; _pr="${WORKFLOW_PROMOTE_ENABLED-}"
if [ -f .env ]; then set -a; . ./.env 2>/dev/null || true; set +a; fi
[ -n "$_ci" ] && WORKFLOW_CI_ENABLED="$_ci"
[ -n "$_cd" ] && WORKFLOW_CD_ENABLED="$_cd"
[ -n "$_pr" ] && WORKFLOW_PROMOTE_ENABLED="$_pr"

MODE="apply"
[ "${1:-}" = "--status" ] && MODE="status"
[ "$MODE" = "apply" ] && [ "${DRY_RUN:-0}" = "1" ] && MODE="dry-run"

flag_name() { echo "WORKFLOW_$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')_ENABLED"; }
flag_raw()  { local v; v="$(flag_name "$1")"; printf '%s' "${!v:-}"; }

# ci -> enable | disable | invalid
want_for() {
  local raw; raw="$(flag_raw "$1")"
  case "$(printf '%s' "${raw:-true}" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|on)  echo enable ;;
    false|0|no|off) echo disable ;;
    *)              echo invalid ;;
  esac
}

# -- validate ALL flags before touching anything -------------------------------------
bad=0
for wf in $WORKFLOWS; do
  if [ "$(want_for "$wf")" = invalid ]; then
    echo "  $(flag_name "$wf")='$(flag_raw "$wf")' is not true/false - refusing to guess."
    bad=1
  fi
done
if [ "$bad" = 1 ]; then
  echo "  Nothing was changed. Use true or false."
  exit 1
fi

# -- dry run: the plan, with no gh call and no network --------------------------------
if [ "$MODE" = "dry-run" ]; then
  echo ""
  echo "  DRY RUN - nothing sent to GitHub"
  echo ""
  for wf in $WORKFLOWS; do
    printf "  %-13s %-32s -> %s\n" "$wf.yml" "$(flag_name "$wf")=$(flag_raw "$wf")" \
      "would $(want_for "$wf")"
  done
  echo ""
  echo "  Apply with:  make gh-workflows"
  exit 0
fi

# -- live modes need an authenticated gh ---------------------------------------------
if ! command -v gh >/dev/null 2>&1; then
  echo "  gh CLI not found. Install it (https://cli.github.com), then: gh auth login"
  exit 1
fi
if ! gh auth status >/dev/null 2>&1; then
  echo "  gh is not authenticated. Run: gh auth login"
  exit 1
fi

# "<file> <state>" per workflow, e.g. "ci.yml active" / "cd.yml disabled_manually".
# \r stripped: gh on Windows can emit CRLF, and "active\r" never equals "active".
live_states() {
  gh workflow list --all --json path,state \
    --jq '.[] | "\(.path | split("/") | last) \(.state)"' | tr -d '\r'
}
state_of() { printf '%s\n' "$STATES" | awk -v f="$1.yml" '$1 == f { print $2 }'; }

if ! STATES="$(live_states)"; then
  echo "  Could not list this repo's workflows. Is it pushed to GitHub, and does"
  echo "  your gh login have access to it?"
  exit 1
fi

print_table() {
  echo ""
  printf "  %-13s %-20s %-10s %s\n" "workflow" "on GitHub" ".env" ""
  printf "  %-13s %-20s %-10s %s\n" "--------" "---------" "----" ""
  for wf in $WORKFLOWS; do
    local cur want sync
    cur="$(state_of "$wf")"; cur="${cur:-not-found}"
    want="$(want_for "$wf")"
    if   [ "$cur" = not-found ];                        then sync="(not on GitHub yet)"
    elif [ "$want" = enable ]  && [ "$cur" = active ];  then sync="in sync"
    elif [ "$want" = disable ] && [ "$cur" != active ]; then sync="in sync"
    else sync="DRIFT - run: make gh-workflows"; fi
    printf "  %-13s %-20s %-10s %s\n" "$wf.yml" "$cur" "${want}d" "$sync"
  done
  echo ""
}

if [ "$MODE" = "status" ]; then
  print_table
  exit 0
fi

# -- apply: change only what differs --------------------------------------------------
echo ""
for wf in $WORKFLOWS; do
  want="$(want_for "$wf")"
  cur="$(state_of "$wf")"
  if [ -z "$cur" ]; then
    echo "  $wf.yml  not found on GitHub (never pushed?) - skipped"
  elif [ "$want" = enable ] && [ "$cur" = active ]; then
    echo "  $wf.yml  already enabled"
  elif [ "$want" = disable ] && [ "$cur" != active ]; then
    echo "  $wf.yml  already disabled ($cur)"
  else
    gh workflow "$want" "$wf.yml" >/dev/null
    echo "  $wf.yml  ${want}d"
  fi
done

# Re-read rather than assume: the table reports what GitHub now says, not what we asked.
STATES="$(live_states)"
print_table
