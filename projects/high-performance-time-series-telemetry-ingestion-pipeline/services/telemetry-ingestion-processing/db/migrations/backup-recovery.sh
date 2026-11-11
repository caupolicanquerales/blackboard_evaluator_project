#!/usr/bin/env bash
# Periodic base snapshot; WAL archiving (archive_mode=on) enables point-in-time recovery.
# Rollback posture is expand-only: forward-fix or restore from this backup.
set -euo pipefail
: "${PGHOST:?}" "${PGUSER:?}" "${BACKUP_DIR:?}"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
pg_basebackup -h "$PGHOST" -U "$PGUSER" -D "$BACKUP_DIR/base-$stamp" -Ft -z -X stream
