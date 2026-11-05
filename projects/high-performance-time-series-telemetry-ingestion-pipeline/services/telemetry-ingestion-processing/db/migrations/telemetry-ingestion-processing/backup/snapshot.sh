#!/usr/bin/env bash
# Periodic base snapshot; run from cron/scheduler. WAL archive (see
# config/postgresql.telemetry.conf) provides log retention for replay.
# Recovery: restore latest snapshot, replay WAL, then rebuild the reorder
# window by replaying the event log.
set -euo pipefail

BACKUP_ROOT="${BACKUP_ROOT:-/backup}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
TARGET="${BACKUP_ROOT}/base/${STAMP}"

mkdir -p "${TARGET}"
pg_basebackup -h "${TELEMETRY_DB_HOST}" -p "${TELEMETRY_DB_PORT:-5432}" \
  -U "${TELEMETRY_DB_USER}" -D "${TARGET}" -Ft -z -X stream -c fast

find "${BACKUP_ROOT}/base" -mindepth 1 -maxdepth 1 -type d -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +
find "${BACKUP_ROOT}/wal" -type f -mtime +"${RETENTION_DAYS}" -delete
