"""Pure negative controls for the two-token HUMAN-approved recovery."""

import unittest
import uuid

from qa.postgres_instance import MARKER, ROLE
from qa.wp7a2_recover import APPROVED, validate_damage, validate_identity, validate_tombstone


class RecoveryTests(unittest.TestCase):
    def test_exact_separately_approved_tombstone(self):
        validate_tombstone("325de41be0b7492f", (8996294, ROLE, -2))

    def test_tombstone_exception_cannot_generalize(self):
        for token, row in (
            ("67abc9a3296a0694", (8996294, ROLE, -2)),
            ("325de41be0b7492f", (8996295, ROLE, -2)),
            ("325de41be0b7492f", (8996294, "postgres", -2)),
            ("325de41be0b7492f", (8996294, ROLE, -1)),
        ):
            with self.assertRaises(ValueError):
                validate_tombstone(token, row)

    def test_only_exact_approved_null_records(self):
        for token, count in APPROVED.items():
            validate_damage(token, bytes(count))

    def test_other_tokens_denied(self):
        with self.assertRaises(ValueError):
            validate_damage("a" * 16, bytes(452))

    def test_valid_or_partially_corrupted_records_not_rewritten(self):
        for value in (b"{}", b"\0" * 451, b"\0" * 451 + b"x"):
            with self.assertRaises(ValueError):
                validate_damage("67abc9a3296a0694", value)

    def test_exact_owned_marker(self):
        validate_identity(
            "67abc9a3296a0694", (123, ROLE, -1), (MARKER, "67abc9a3296a0694", str(uuid.uuid4()))
        )

    def test_wrong_owner_denied(self):
        with self.assertRaises(ValueError):
            validate_identity(
                "67abc9a3296a0694",
                (123, "postgres", -1),
                (MARKER, "67abc9a3296a0694", str(uuid.uuid4())),
            )

    def test_wrong_marker_or_token_denied(self):
        for marker in (
            ("other", "67abc9a3296a0694", str(uuid.uuid4())),
            (MARKER, "b" * 16, str(uuid.uuid4())),
        ):
            with self.assertRaises(ValueError):
                validate_identity("67abc9a3296a0694", (123, ROLE, -1), marker)

    def test_invalid_tombstone_denied(self):
        with self.assertRaises(ValueError):
            validate_identity(
                "67abc9a3296a0694", (123, ROLE, -2), (MARKER, "67abc9a3296a0694", str(uuid.uuid4()))
            )

    def test_missing_creation_identity_denied(self):
        with self.assertRaises(ValueError):
            validate_identity(
                "67abc9a3296a0694", (123, ROLE, -1), (MARKER, "67abc9a3296a0694", "not-a-uuid")
            )
