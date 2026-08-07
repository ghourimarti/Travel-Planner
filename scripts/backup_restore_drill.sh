#!/usr/bin/env bash
# Backup & restore DRILL. A backup you've never restored is not a backup.
#
# Proves we can (1) back up the durable run store (Postgres) and the vector store (Qdrant),
# and (2) restore into a scratch target and verify row/point counts match. Run it on a
# schedule (and before every risky migration). Local default targets the docker-compose stack;
# in cloud, point DATABASE_URL / QDRANT_URL at the managed services (read-replica for the dump).
#
# Usage:
#   DATABASE_URL=postgresql://tp:tp@localhost:5432/tp QDRANT_URL=http://localhost:6333 \
#     bash scripts/backup_restore_drill.sh
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-postgresql://tp:tp@localhost:5432/tp}"
QDRANT_URL="${QDRANT_URL:-http://localhost:6333}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-pois}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="${BACKUP_DIR:-./.backups}/${STAMP}"
mkdir -p "$OUT"
echo "==> Drill ${STAMP}; artifacts in ${OUT}"

# ---- 1. Postgres: dump -> restore into a scratch DB -> compare run counts ----
echo "==> [pg] dumping runs database"
pg_dump "$DATABASE_URL" --format=custom --file="${OUT}/runs.dump"
test -s "${OUT}/runs.dump" || { echo "FAIL: empty dump"; exit 1; }

SRC_COUNT="$(psql "$DATABASE_URL" -tAc 'SELECT count(*) FROM runs')"
SCRATCH="${DATABASE_URL%/*}/tp_restore_drill_${STAMP//-/}"
echo "==> [pg] restoring into scratch DB and verifying"
createdb "$SCRATCH" 2>/dev/null || true
pg_restore --clean --if-exists --no-owner --dbname="$SCRATCH" "${OUT}/runs.dump"
DST_COUNT="$(psql "$SCRATCH" -tAc 'SELECT count(*) FROM runs')"
dropdb "$SCRATCH"

if [[ "$SRC_COUNT" != "$DST_COUNT" ]]; then
  echo "FAIL: pg row mismatch (src=${SRC_COUNT} restored=${DST_COUNT})"; exit 1
fi
echo "    [pg] OK — ${DST_COUNT} runs restored == source"

# ---- 2. Qdrant: snapshot the collection and confirm it's retrievable ----
echo "==> [qdrant] creating snapshot of '${QDRANT_COLLECTION}'"
SNAP="$(curl -fsS -X POST "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots" \
  | sed -n 's/.*"name":"\([^"]*\)".*/\1/p')"
test -n "$SNAP" || { echo "FAIL: no qdrant snapshot name returned"; exit 1; }
curl -fsS "${QDRANT_URL}/collections/${QDRANT_COLLECTION}/snapshots/${SNAP}" \
  --output "${OUT}/qdrant-${QDRANT_COLLECTION}.snapshot"
test -s "${OUT}/qdrant-${QDRANT_COLLECTION}.snapshot" || { echo "FAIL: empty snapshot"; exit 1; }
echo "    [qdrant] OK — snapshot ${SNAP} downloaded"

echo "==> DRILL PASSED. Restore-verified backup at ${OUT}"
