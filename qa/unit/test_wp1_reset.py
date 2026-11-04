"""The disposable reset must not target PostgreSQL server-owned processes."""

import os
import unittest
from unittest.mock import MagicMock, patch

from vayujit_api.core.test_database import terminate_test_database_sessions


class Wp1ResetTests(unittest.TestCase):
    def test_termination_is_exact_database_current_role_client_sessions_only(self):
        engine = MagicMock()
        connection = engine.begin.return_value.__enter__.return_value
        connection.execute.return_value = [(True,)]
        with (
            patch.dict(os.environ, {"VAYUJIT_ENV": "test"}),
            patch("vayujit_api.core.test_database.create_engine", return_value=engine),
        ):
            self.assertEqual(
                terminate_test_database_sessions(
                    "postgresql://qa@127.0.0.1/vayujit_qa0123456789abcdef_test"
                ),
                1,
            )
        statement, parameters = connection.execute.call_args.args
        self.assertIn("usename = current_user", str(statement))
        self.assertIn("backend_type = 'client backend'", str(statement))
        self.assertIn("pid <> pg_backend_pid()", str(statement))
        self.assertEqual(parameters, {"database": "vayujit_qa0123456789abcdef_test"})
