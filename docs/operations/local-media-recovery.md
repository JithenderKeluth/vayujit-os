# Local filesystem media recovery

The available local storage backend is the filesystem. The local drill uses
apps/api/vayujit_api/operations/media_backup.py and the wrappers
scripts/backup-media-disposable.ps1 and scripts/restore-media-disposable.ps1.

1. Quiesce writes and record the database and media timestamps.
2. Create a PostgreSQL custom-format dump with scripts/backup-disposable.ps1.
3. Create a ZIP archive plus checksum/MIME/size manifest with the media backup wrapper.
4. Restore both into isolated disposable targets.
5. Verify database Media rows, file existence, SHA-256 checksums, sizes, MIME types,
   Product/owner lineage, and orphan-file count before resuming writes.

The archive refuses symlinks, path traversal, corrupt manifests, checksum/size
mismatches, and non-empty restore targets. Failed restores stage into a temporary
directory and do not partially overwrite the target. Backup retention remains
explicitly configured by VAYUJIT_BACKUP_RETENTION_COUNT and
VAYUJIT_BACKUP_RETENTION_DAYS; maintenance-cleanup --dry-run previews deletion.

The database and media backups are quiesced and eventually consistent, not an
atomic multi-system snapshot. Production procedure must pause writes, create both
artifacts, record the pair, verify both in an isolated restore, and only then
resume traffic. Production object-storage restore remains NOT VALIDATED.
