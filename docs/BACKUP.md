# Backup

Photos live on your server's filesystem, so a backup has two halves that must
be taken together:

1. **PostgreSQL** — accounts, events, photo records, face vectors, matches.
2. **`storage/`** — the actual image files.

A database without the files leaves broken galleries. Files without the
database leave photos nobody can find. Always restore both.

> Nothing in ALLBEE deletes photos on its own. `GUEST_DATA_RETENTION_DAYS`
> defaults to `0`, which means never. See [PRIVACY.md](PRIVACY.md).

## Quick manual backup

**Linux / macOS:**

```bash
pg_dump -U allbee -Fc allbee > allbee-$(date +%F).dump
tar czf allbee-storage-$(date +%F).tar.gz -C /var/lib/allbee storage
```

**Windows (PowerShell):**

```powershell
$date = Get-Date -Format yyyy-MM-dd
pg_dump -U allbee -Fc allbee > "allbee-$date.dump"
Compress-Archive -Path .\backend\storage -DestinationPath "allbee-storage-$date.zip"
```

## Restore

```bash
createdb -U allbee allbee_restored
pg_restore -U allbee -d allbee_restored --no-owner allbee-2026-09-01.dump
tar xzf allbee-storage-2026-09-01.tar.gz -C /var/lib/allbee
```

Point `DATABASE_URL` and `STORAGE_PATH` at the restored copies and start the
API. Because stored paths are relative, the storage directory can land
anywhere.

## Automated nightly backup

`/opt/allbee/backup.sh`:

```bash
#!/usr/bin/env bash
# Nightly backup of the ALLBEE database and photo storage.
set -euo pipefail

BACKUP_DIR=/var/backups/allbee
STORAGE_DIR=/var/lib/allbee/storage
KEEP_DAYS=14
STAMP=$(date +%F-%H%M)

mkdir -p "$BACKUP_DIR"

# Database. -Fc is compressed and restores selectively.
pg_dump -U allbee -Fc allbee > "$BACKUP_DIR/db-$STAMP.dump"

# Photos. A hard-link snapshot against the previous run, so each nightly copy
# only costs disk for files that actually changed.
LATEST="$BACKUP_DIR/storage-latest"
rsync -a --delete \
      ${LATEST:+--link-dest="$LATEST"} \
      "$STORAGE_DIR/" "$BACKUP_DIR/storage-$STAMP/"
ln -sfn "$BACKUP_DIR/storage-$STAMP" "$LATEST"

# Prune. Only ever touches the backup directory, never live storage.
find "$BACKUP_DIR" -maxdepth 1 -name 'db-*.dump' -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -maxdepth 1 -name 'storage-2*' -maxdepth 1 -type d \
     -mtime +$KEEP_DAYS -exec rm -rf {} +

echo "Backup complete: $STAMP"
```

```bash
sudo chmod +x /opt/allbee/backup.sh
sudo crontab -e
# 03:15 every night
15 3 * * * /opt/allbee/backup.sh >> /var/log/allbee-backup.log 2>&1
```

## Off-site copy

A backup on the same disk protects against mistakes, not hardware failure.
Push the backup directory somewhere else — another machine, a NAS, or any
S3-compatible object store you run yourself (MinIO, Garage, Ceph):

```bash
rsync -az --delete /var/backups/allbee/ backup-host:/srv/allbee-backups/
```

## Before a big event

Take a manual backup before an event starts. Restoring to "yesterday" is
painless; losing the first two hours of a wedding is not.

## Check your backups

An untested backup is a guess. Once a quarter:

```bash
createdb -U allbee allbee_test
pg_restore -U allbee -d allbee_test --no-owner /var/backups/allbee/db-<latest>.dump
psql -U allbee -d allbee_test -c "SELECT count(*) FROM photos;"
dropdb -U allbee allbee_test
```

Compare that count against the live database, and spot-check that a few files
named in `photos.original_path` exist under the backed-up storage tree.
