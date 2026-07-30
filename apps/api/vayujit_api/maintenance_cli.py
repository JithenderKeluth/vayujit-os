import argparse
import json
import sys
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from vayujit_api.core.config import get_settings
from vayujit_api.core.database import SessionFactory
from vayujit_api.core.observability import maintenance_enabled, maintenance_marker
from vayujit_api.identity.models import AuthSession, User
from vayujit_api.operations.backup import backup_path, create_backup, verify_backup
from vayujit_api.operations.models import BackupRecord


def output(**values: object) -> None:
    print(json.dumps(values, default=str))


def require_confirmation(args: argparse.Namespace) -> None:
    if not args.confirm:
        raise RuntimeError("This command requires --confirm.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--latest", action="store_true")
    args = parser.parse_args()
    marker = maintenance_marker()
    try:
        if args.command == "maintenance-status":
            output(status="PASS", maintenance=maintenance_enabled())
            return 0
        if args.command == "maintenance-on":
            require_confirmation(args)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(datetime.now(UTC).isoformat(), encoding="utf-8")
            output(status="PASS", maintenance=True)
            return 0
        if args.command == "maintenance-off":
            require_confirmation(args)
            marker.unlink(missing_ok=True)
            output(status="PASS", maintenance=False)
            return 0
        with SessionFactory() as db:
            if args.command == "migration-status":
                output(
                    status="PASS",
                    revision=db.scalar(text("select version_num from alembic_version")),
                )
                return 0
            if args.command in {
                "backup-create",
                "backup-list",
                "backup-verify",
                "backup-restore-plan",
            }:
                owner = db.scalar(select(User).order_by(User.created_at).limit(1))
                if owner is None:
                    raise RuntimeError("No local owner exists.")
                if args.command == "backup-create":
                    value = create_backup(db, owner.id)
                    db.commit()
                    output(status="PASS", backup_id=value.id, backup_key=value.backup_key)
                    return 0
                values = list(
                    db.scalars(
                        select(BackupRecord)
                        .where(BackupRecord.owner_id == owner.id)
                        .order_by(BackupRecord.created_at.desc())
                    )
                )
                if args.command == "backup-list":
                    output(
                        status="PASS",
                        backups=[
                            {
                                "id": str(item.id),
                                "key": item.backup_key,
                                "status": item.status,
                                "size_bytes": item.size_bytes,
                            }
                            for item in values
                        ],
                    )
                    return 0
                if not values:
                    raise RuntimeError("No backup is available.")
                value = values[0]
                valid = verify_backup(value)
                db.commit()
                if args.command == "backup-verify":
                    output(status="PASS" if valid else "FAIL", backup_id=value.id, valid=valid)
                    return 0 if valid else 1
                output(
                    status="PASS" if valid else "FAIL",
                    backup_id=value.id,
                    checksum_valid=valid,
                    execution_supported=False,
                    operator_action="Use the documented guarded disposable restore-test procedure.",
                )
                return 0 if valid else 1
            if args.command == "sessions-cleanup":
                expired = list(
                    db.scalars(
                        select(AuthSession).where(AuthSession.expires_at < datetime.now(UTC))
                    )
                )
                if not args.dry_run:
                    for item in expired:
                        db.delete(item)
                    db.commit()
                output(
                    status="PASS",
                    candidates=len(expired),
                    deleted=0 if args.dry_run else len(expired),
                )
                return 0
            if args.command == "maintenance-cleanup":
                settings = get_settings()
                backups = list(
                    db.scalars(select(BackupRecord).order_by(BackupRecord.created_at.desc()))
                )
                cutoff = datetime.now(UTC) - timedelta(days=settings.backup_retention_days)
                candidates = [
                    item
                    for index, item in enumerate(backups)
                    if item.verification_status == "verified"
                    and (index >= settings.backup_retention_count or item.created_at < cutoff)
                ]
                candidate_size = sum(item.size_bytes for item in candidates)
                deleted_count = 0
                reclaimed_size = 0
                errors: list[str] = []
                if not args.dry_run:
                    for backup_record in candidates:
                        try:
                            backup_path(backup_record.filename).unlink(missing_ok=True)
                            backup_path(f"{backup_record.filename}.json").unlink(missing_ok=True)
                            db.delete(backup_record)
                            deleted_count += 1
                            reclaimed_size += backup_record.size_bytes
                        except OSError:
                            errors.append(backup_record.backup_key)
                    db.commit()
                output(
                    status="PASS" if not errors else "FAIL",
                    dry_run=args.dry_run,
                    candidate_count=len(candidates),
                    candidate_size=candidate_size,
                    deleted_count=deleted_count,
                    reclaimed_size=reclaimed_size,
                    skipped_items=len(backups) - len(candidates),
                    errors=errors,
                )
                return 0 if not errors else 1
        raise RuntimeError("Unknown maintenance command.")
    except Exception as error:
        output(status="FAIL", message=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
