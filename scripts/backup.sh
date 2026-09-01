#!/usr/bin/env bash
# Nightly backup of the ALLBEE database and photo storage.
# Both halves are taken together: a database without files leaves broken
# galleries, and files without the database leave photos nobody can find.
#
#   sudo crontab -e
#   15 3 * * * /opt/allbee/app/scripts/backup.sh >> /var/log/allbee-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${ALLBEE_BACKUP_DIR:-/var/backups/allbee}"
STORAGE_DIR="${ALLBEE_STORAGE_DIR:-/var/lib/allbee/storage}"
DB_NAME="${ALLBEE_DB_NAME:-allbee}"
DB_USER="${ALLBEE_DB_USER:-allbee}"
KEEP_DAYS="${ALLBEE_KEEP_DAYS:-14}"
STAMP=$(date +%F-%H%M)

mkdir -p "$BACKUP_DIR"

echo "[$(date -Is)] Backing up database $DB_NAME"
pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$BACKUP_DIR/db-$STAMP.dump"

echo "[$(date -Is)] Backing up storage from $STORAGE_DIR"
LATEST="$BACKUP_DIR/storage-latest"
if [ -d "$LATEST" ]; then
  # Hard-link against last night's copy: unchanged photos cost no extra disk.
  rsync -a --delete --link-dest="$LATEST" "$STORAGE_DIR/" "$BACKUP_DIR/storage-$STAMP/"
else
  rsync -a --delete "$STORAGE_DIR/" "$BACKUP_DIR/storage-$STAMP/"
fi
ln -sfn "$BACKUP_DIR/storage-$STAMP" "$LATEST"

echo "[$(date -Is)] Pruning backups older than $KEEP_DAYS days"
# Scoped to the backup directory only. Live storage is never touched.
find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.dump' -mtime +"$KEEP_DAYS" -delete
find "$BACKUP_DIR" -maxdepth 1 -type d -name 'storage-2*' -mtime +"$KEEP_DAYS" \
     -exec rm -rf {} +

echo "[$(date -Is)] Backup complete: $STAMP"
du -sh "$BACKUP_DIR"
