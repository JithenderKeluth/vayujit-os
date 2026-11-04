"""WP0A negative safety checks. No database, Docker, or production imports."""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from sqlalchemy.engine import URL

from qa import postgres_instance as guard
from qa.validate_postgres_instance import QaMigrationConfig


class InstanceSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(patch.stopall)
        patch.object(guard, "PRIVATE", Path(self.temp.name)).start()
        self.instance = object.__new__(guard.QaInstance)
        self.instance.key = b"synthetic-unit-only"
        self.instance.manifest = {
            "instance_id": "unit-instance",
            "container_id": "unit-container",
        }
        self.token = "0123456789abcdef"
        self.record = {
            "instance_id": "unit-instance",
            "container_id": "unit-container",
            "database": guard.database_name(self.token),
            "owner": guard.ROLE,
            "token": self.token,
            "state": "ACTIVE",
            "oid": 123,
            "creation_id": "unit-creation",
        }

    def test_exact_database_name(self):
        self.assertEqual(guard.database_name(self.token), "vayujit_qa0123456789abcdef_test")

    def test_invalid_tokens(self):
        for token in (
            "",
            "A" * 16,
            "../postgres",
            "0" * 15,
            "0" * 17,
            "x;DROP DATABASE",
        ):
            with self.subTest(token=token), self.assertRaises(guard.GuardDenied):
                guard.database_name(token)

    def test_signature_roundtrip(self):
        self.assertEqual(
            guard.verified(guard.signed(self.record, self.instance.key), self.instance.key)[
                "owner"
            ],
            guard.ROLE,
        )

    def test_tampering_denied(self):
        record = guard.signed(self.record, self.instance.key)
        record["owner"] = "postgres"
        with self.assertRaisesRegex(guard.GuardDenied, "QA_SIGNATURE_DENIED"):
            guard.verified(record, self.instance.key)

    def test_wrong_signing_key_denied(self):
        with self.assertRaises(guard.GuardDenied):
            guard.verified(guard.signed(self.record, b"other"), self.instance.key)

    def test_unsigned_record_denied(self):
        with self.assertRaises(guard.GuardDenied):
            guard.verified(self.record, self.instance.key)

    def test_signed_lifecycle_roundtrip(self):
        self.instance.save(self.token, self.record, new=True)
        self.assertEqual(self.instance.load(self.token)["oid"], 123)

    def test_lifecycle_owner_mismatch_denied(self):
        self.instance.save(self.token, dict(self.record, owner="postgres"))
        with self.assertRaisesRegex(guard.GuardDenied, "QA_LIFECYCLE_ID_DENIED"):
            self.instance.load(self.token)

    def test_lifecycle_container_mismatch_denied(self):
        self.instance.save(self.token, dict(self.record, container_id="another"))
        with self.assertRaises(guard.GuardDenied):
            self.instance.load(self.token)

    def test_lifecycle_token_mismatch_denied(self):
        self.instance.save(self.token, dict(self.record, token="f" * 16))
        with self.assertRaises(guard.GuardDenied):
            self.instance.load(self.token)

    def test_missing_ledger_cannot_delete(self):
        self.instance.engine = Mock(side_effect=AssertionError("SQL must not run"))
        with self.assertRaises(FileNotFoundError):
            self.instance.drop(self.token)
        self.instance.engine.assert_not_called()

    def test_forbidden_names_cannot_reach_sql(self):
        self.instance.engine = Mock(side_effect=AssertionError("SQL must not run"))
        for name in (
            "postgres",
            "vayujit",
            "vayujit_golden_test",
            "template1",
            "vayujit_qa" + "f" * 16 + "_test",
        ):
            with (
                self.subTest(name=name),
                self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_NAME_DENIED"),
            ):
                self.instance.drop(self.token, requested_name=name)
        self.instance.engine.assert_not_called()

    def test_nonactive_lifecycle_cannot_reach_sql(self):
        self.instance.verify_server = Mock(side_effect=AssertionError("SQL must not run"))
        for state in ("CREATING", "DROPPING", "DROPPED", "UNKNOWN"):
            self.instance.save(self.token, dict(self.record, state=state))
            with (
                self.subTest(state=state),
                self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_STATE_DENIED"),
            ):
                self.instance.drop(self.token)
        self.instance.verify_server.assert_not_called()

    def test_duplicate_ledger_creation_refused(self):
        self.instance.save(self.token, self.record, new=True)
        with self.assertRaises(FileExistsError):
            self.instance.save(self.token, self.record, new=True)

    def test_normal_drop_deadline_is_bounded_before_any_sql(self):
        self.instance.engine = Mock(side_effect=AssertionError("SQL must not run"))
        for timeout in (0, 14999, 90001, True, "90000"):
            with self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_TIMEOUT_DENIED"):
                self.instance.drop(self.token, timeout_ms=timeout)
        self.instance.engine.assert_not_called()

    def test_normal_extended_deadline_keeps_marker_identity_and_nonforce_drop(self):
        self.instance.save(self.token, self.record)
        self.instance.verify_server = Mock()
        admin, target = MagicMock(), MagicMock()
        c = admin.connect.return_value.execution_options.return_value.__enter__.return_value
        t = target.connect.return_value.__enter__.return_value
        c.execute.return_value.one.return_value = (123, guard.ROLE, -1)
        t.execute.return_value.one.return_value = (
            guard.MARKER,
            self.token,
            self.record["creation_id"],
        )
        c.scalar.side_effect = [0, 0]
        self.instance.engine = Mock(side_effect=[admin, target])
        self.instance.drop(self.token, timeout_ms=90000)
        self.instance.verify_server.assert_called_once()
        statements = [str(call.args[0]) for call in c.execute.call_args_list]
        self.assertTrue(any("set_config('statement_timeout'" in s for s in statements))
        self.assertIn(f'DROP DATABASE "{guard.database_name(self.token)}"', statements)
        self.assertFalse(any("FORCE" in s or "terminate" in s for s in statements))
        self.assertEqual(self.instance.load(self.token)["state"], "DROPPED")
        self.assertEqual(self.instance.load(self.token)["drop_statement_timeout_ms"], 90000)

    def test_extended_normal_deadline_never_bypasses_active_session_denial(self):
        self.instance.save(self.token, self.record)
        self.instance.verify_server = Mock()
        admin, target = MagicMock(), MagicMock()
        c = admin.connect.return_value.execution_options.return_value.__enter__.return_value
        t = target.connect.return_value.__enter__.return_value
        c.execute.return_value.one.return_value = (123, guard.ROLE, -1)
        t.execute.return_value.one.return_value = (
            guard.MARKER,
            self.token,
            self.record["creation_id"],
        )
        c.scalar.return_value = 1
        self.instance.engine = Mock(side_effect=[admin, target])
        with self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_ACTIVE_SESSIONS"):
            self.instance.drop(self.token, timeout_ms=90000)
        self.assertFalse(
            any("DROP DATABASE" in str(call.args[0]) for call in c.execute.call_args_list)
        )
        self.assertEqual(self.instance.load(self.token)["state"], "ACTIVE")

    def test_explicit_resume_rejects_every_non_dropping_state_before_sql(self):
        self.instance.verify_server = Mock(side_effect=AssertionError("SQL must not run"))
        for state in ("ACTIVE", "CREATING", "DROPPED", "UNKNOWN"):
            self.instance.save(self.token, dict(self.record, state=state))
            with (
                self.subTest(state=state),
                self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_STATE_DENIED"),
            ):
                self.instance.resume_drop(self.token)
        self.instance.verify_server.assert_not_called()

    def test_explicit_resume_rechecks_instance_and_never_resets_lifecycle(self):
        self.instance.save(self.token, dict(self.record, state="DROPPING"))
        self.instance.verify_server = Mock(side_effect=guard.GuardDenied("INSTANCE_CHANGED"))
        with self.assertRaisesRegex(guard.GuardDenied, "INSTANCE_CHANGED"):
            self.instance.resume_drop(self.token)
        self.assertEqual(self.instance.load(self.token)["state"], "DROPPING")

    def test_invalid_tombstone_resume_uses_prior_signed_stage_and_same_owner_oid(self):
        self.instance.save(self.token, dict(self.record, state="DROPPING"))
        self.instance.verify_server = Mock()
        engine = MagicMock()
        c = engine.connect.return_value.execution_options.return_value.__enter__.return_value
        c.execute.return_value.one.return_value = (123, guard.ROLE, -2)
        c.scalar.side_effect = [0, 0]
        self.instance.engine = Mock(return_value=engine)
        self.instance.resume_drop(self.token)
        self.instance.engine.assert_called_once_with()
        sql = [str(call.args[0]) for call in c.execute.call_args_list]
        self.assertIn(f'DROP DATABASE "{guard.database_name(self.token)}"', sql)
        self.assertFalse(any("FORCE" in statement for statement in sql))
        record = self.instance.load(self.token)
        self.assertEqual(record["state"], "DROPPED")
        self.assertTrue(record["invalid_tombstone_recovery"])

    def test_invalid_tombstone_with_different_oid_is_never_deleted(self):
        self.instance.save(self.token, dict(self.record, state="DROPPING"))
        self.instance.verify_server = Mock()
        engine = MagicMock()
        c = engine.connect.return_value.execution_options.return_value.__enter__.return_value
        c.execute.return_value.one.return_value = (999, guard.ROLE, -2)
        self.instance.engine = Mock(return_value=engine)
        with self.assertRaisesRegex(guard.GuardDenied, "QA_DELETE_OWNER_OID_DENIED"):
            self.instance.resume_drop(self.token)
        self.assertFalse(
            any("DROP DATABASE" in str(call.args[0]) for call in c.execute.call_args_list)
        )

    def test_recovery_timeout_is_bounded_and_requires_all_existing_identity_guards(
        self,
    ):
        for timeout in (0, 14999, 90001, True, "90000"):
            with self.assertRaisesRegex(guard.GuardDenied, "QA_RECOVERY_TIMEOUT_DENIED"):
                self.instance.resume_drop(self.token, timeout_ms=timeout)
        self.instance.save(self.token, dict(self.record, state="DROPPING"))
        self.instance.verify_server = Mock()
        engine = MagicMock()
        c = engine.connect.return_value.execution_options.return_value.__enter__.return_value
        c.execute.return_value.one.return_value = (123, guard.ROLE, -2)
        c.scalar.side_effect = [0, 0]
        self.instance.engine = Mock(return_value=engine)
        self.instance.resume_drop(self.token, timeout_ms=90000)
        self.instance.verify_server.assert_called_once()
        self.assertEqual(self.instance.load(self.token)["recovery_statement_timeout_ms"], 90000)
        self.assertTrue(
            any(
                call.args[1] == {"ms": "90000"}
                for call in c.execute.call_args_list
                if len(call.args) == 2
            )
        )

    def test_concurrent_lease_denied(self):
        with (
            self.instance.lease(self.token),
            self.assertRaisesRegex(guard.GuardDenied, "QA_LIFECYCLE_BUSY"),
            self.instance.lease(self.token),
        ):
            self.fail("lease entered twice")
        self.assertFalse(self.instance.ledger_path(self.token).with_suffix(".lock").exists())

    def test_failed_operation_releases_lease(self):
        with self.assertRaises(ValueError), self.instance.lease(self.token):
            raise ValueError("synthetic")
        self.assertFalse(self.instance.ledger_path(self.token).with_suffix(".lock").exists())

    def test_dedicated_role_requires_manifest(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(guard.GuardDenied, "QA_MANIFEST_REQUIRED"),
        ):
            guard.approved_guard(URL.create("postgresql+psycopg", username=guard.ROLE))

    def test_wrong_manifest_denied(self):
        with (
            patch.dict(os.environ, {"QA_POSTGRES_INSTANCE_MANIFEST": "wrong.json"}),
            self.assertRaises(guard.GuardDenied),
        ):
            guard.approved_guard(URL.create("postgresql+psycopg", username=guard.ROLE))

    def test_percent_encoded_password_preserved(self):
        cfg = QaMigrationConfig()
        value = "postgresql+psycopg://qa:synthetic%2F%2B@127.0.0.1/qa_test"
        cfg.set_main_option("sqlalchemy.url", value)
        self.assertEqual(cfg.get_main_option("sqlalchemy.url"), value)

    def test_serialized_ledger_has_no_credentials(self):
        self.instance.save(self.token, self.record)
        data = json.loads(self.instance.ledger_path(self.token).read_text())
        self.assertEqual(set(data), set(self.record) | {"signature"})


if __name__ == "__main__":
    unittest.main()
