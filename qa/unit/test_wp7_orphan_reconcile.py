"""No Docker/database changes: exact orphan attestation safety regressions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from qa import postgres_instance as guard
from qa import wp7_orphan_reconcile as recovery


class OrphanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        self.root = Path(self.temp.name)
        patch.object(guard, "PRIVATE", self.root).start()
        self.token = recovery.AUTHORIZED_TOKEN
        self.instance = object.__new__(guard.QaInstance)
        self.instance.key = b"synthetic-unit-only"
        self.instance.manifest = {"instance_id": "unit", "container_id": "unit"}
        self.instance.verify_server = Mock()
        self.record = {
            "instance_id": "unit",
            "container_id": "unit",
            "owner": guard.ROLE,
            "database": guard.database_name(self.token),
            "token": self.token,
            "state": "DROPPING",
            "oid": 123,
            "creation_id": "00000000-0000-0000-0000-000000000001",
        }
        self.instance.save(self.token, self.record)
        self.ledger = self.instance.ledger_path(self.token)
        self.lock = self.ledger.with_suffix(".lock")
        self.lock.write_text("owned-lifecycle-operation")
        self.folder = self.root / "evidence" / self.token
        self.folder.mkdir(parents=True)
        (self.folder / "wp7-run.json").write_text(json.dumps({"token": self.token}))
        self.failure = self.folder / "session-final.json"
        self.failure.write_text(
            json.dumps(
                {
                    "token": self.token,
                    "child_exit": "TIMEOUT",
                    "status": "CLEANUP_BLOCKED",
                }
            )
        )
        self.original = self.failure.read_bytes()
        self.engine = MagicMock()
        self.connection = self.engine.connect.return_value.__enter__.return_value
        self.connection.scalar.side_effect = [False, 0]
        self.instance.engine = Mock(return_value=self.engine)
        self.process = Mock(return_value=False)

    def run_recovery(self, **kwargs):
        return recovery.reconcile(
            self.instance,
            kwargs.pop("token", self.token),
            approved=kwargs.pop("approved", True),
            evidence_root=self.root / "evidence",
            process_check=self.process,
            **kwargs,
        )

    def test_success_only_attests_absence_and_preserves_original_evidence(self):
        other = self.root / "other-record.json"
        other.write_text("unchanged")
        result = self.run_recovery()
        self.assertEqual(result["status"], "ABSENCE_RECONCILED")
        self.assertFalse(self.lock.exists())
        self.assertEqual(self.instance.load(self.token)["cleanup_resolution"], recovery.RESOLUTION)
        self.assertEqual(self.failure.read_bytes(), self.original)
        self.assertEqual(other.read_text(), "unchanged")
        sql = [str(c.args[0]) for c in self.connection.execute.call_args_list]
        self.assertEqual(sql, ["SET TRANSACTION READ ONLY"])
        self.assertFalse(
            any("DROP " in str(c) or "DELETE " in str(c) for c in self.connection.mock_calls)
        )

    def test_explicit_exact_authorization_required(self):
        for options in ({"approved": False}, {"token": "0" * 16}):
            with self.assertRaisesRegex(guard.GuardDenied, "AUTHORIZATION_REQUIRED"):
                self.run_recovery(**options)
        self.instance.engine.assert_not_called()

    def test_database_exists_fails_closed(self):
        self.connection.scalar.side_effect = [True]
        with self.assertRaisesRegex(guard.GuardDenied, "DATABASE_STILL_EXISTS"):
            self.run_recovery()
        self.assertTrue(self.lock.exists())
        self.assertEqual(self.instance.load(self.token)["state"], "DROPPING")

    def test_database_operation_fails_closed(self):
        self.connection.scalar.side_effect = [False, 1]
        with self.assertRaisesRegex(guard.GuardDenied, "ACTIVE_DATABASE_OPERATION"):
            self.run_recovery()
        self.assertTrue(self.lock.exists())

    def test_live_owner_process_denied_before_sql(self):
        self.process.return_value = True
        with self.assertRaisesRegex(guard.GuardDenied, "ACTIVE_OWNER_PROCESS"):
            self.run_recovery()
        self.instance.engine.assert_not_called()

    def test_legacy_lock_content_required(self):
        self.lock.write_text("unknown lock")
        with self.assertRaisesRegex(guard.GuardDenied, "LOCK_CONTENT_DENIED"):
            self.run_recovery()
        self.instance.engine.assert_not_called()

    def test_signature_tampering_rejected(self):
        record = json.loads(self.ledger.read_text())
        record["owner"] = "postgres"
        self.ledger.write_text(json.dumps(record))
        with self.assertRaisesRegex(guard.GuardDenied, "SIGNATURE_DENIED"):
            self.run_recovery()

    def test_non_orphan_state_rejected(self):
        self.instance.save(self.token, {**self.record, "state": "ACTIVE"})
        with self.assertRaisesRegex(guard.GuardDenied, "ORPHAN_STATE_DENIED"):
            self.run_recovery()

    def test_changed_lock_rejected(self):
        self.process.side_effect = lambda _: self.lock.write_text("replaced") and False
        with self.assertRaisesRegex(guard.GuardDenied, "LOCK_CHANGED"):
            self.run_recovery()

    def test_failed_save_keeps_original_lock_and_state(self):
        self.instance.save = Mock(side_effect=OSError("synthetic failure"))
        with self.assertRaises(OSError):
            self.run_recovery()
        self.assertTrue(self.lock.exists())
        self.assertEqual(self.instance.load(self.token)["state"], "DROPPING")
        self.assertEqual(self.failure.read_bytes(), self.original)

    def test_original_failure_required(self):
        self.failure.write_text(json.dumps({"token": self.token, "status": "PASS"}))
        with self.assertRaisesRegex(guard.GuardDenied, "INTERRUPTION_EVIDENCE_REQUIRED"):
            self.run_recovery()

    def test_concurrent_reconciliation_denied(self):
        exclusive = self.ledger.with_suffix(".reconcile.lock")
        exclusive.write_text("another recovery")
        with self.assertRaises(FileExistsError):
            self.run_recovery()
        self.instance.engine.assert_not_called()

    def test_repeat_is_not_reclassified_as_normal_cleanup(self):
        self.run_recovery()
        with self.assertRaisesRegex(guard.GuardDenied, "ORPHAN_STATE_DENIED"):
            self.run_recovery()


if __name__ == "__main__":
    unittest.main()
