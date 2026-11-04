"""Pure harness safety checks; no application/database initialization."""

import importlib.util
import socket
import unittest
from pathlib import Path

from qa.network_guard import restrict_egress

spec = importlib.util.spec_from_file_location("qa_fixture", Path("qa/fixture_server.py"))
assert spec and spec.loader
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class TargetTests(unittest.TestCase):
    def test_only_exact_fresh_token_database_is_allowed(self) -> None:
        fixture.require_target("vayujit_qa0123456789abcdef_test", "0123456789abcdef")

    def test_business_golden_other_test_and_template_targets_denied(self) -> None:
        for target in ["vayujit", "vayujit_golden_test", "postgres", "vayujit_test", "template0"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                fixture.require_target(target, "0123456789abcdef")

    def test_invalid_token_and_injected_identifiers_denied(self) -> None:
        for token in ["", "../business", "A" * 16, "0123456789abcdef;DROP", "0" * 15]:
            with self.subTest(token=token), self.assertRaises(ValueError):
                fixture.require_target(f"vayujit_qa{token}_test", token)


class EgressTests(unittest.TestCase):
    def setUp(self) -> None:
        self.restore = restrict_egress(5432)

    def tearDown(self) -> None:
        self.restore()

    def test_stdlib_socketpair_works_with_windows_default(self) -> None:
        left, right = socket.socketpair()
        try:
            left.sendall(b"qa")
            self.assertEqual(right.recv(2), b"qa")
        finally:
            left.close()
            right.close()

    def test_tcp_connect_and_connect_ex_deny_external_and_other_local_ports(self) -> None:
        with socket.socket() as client:
            for address in [("203.0.113.1", 443), ("127.0.0.1", 8000)]:
                with (
                    self.subTest(address=address),
                    self.assertRaisesRegex(OSError, "QA_EGRESS_DENIED"),
                ):
                    client.connect(address)
                with (
                    self.subTest(address=address),
                    self.assertRaisesRegex(OSError, "QA_EGRESS_DENIED"),
                ):
                    client.connect_ex(address)

    def test_external_dns_denied_before_resolution(self) -> None:
        with self.assertRaisesRegex(OSError, "QA_DNS_EGRESS_DENIED"):
            socket.getaddrinfo("qa-invalid.example.com", 443)

    def test_fixture_dns_is_opt_in(self) -> None:
        with self.assertRaisesRegex(OSError, "QA_DNS_EGRESS_DENIED"):
            socket.getaddrinfo("example.org", 443)


class SyntheticSupplierDnsTests(unittest.TestCase):
    def test_exact_fixture_dns_never_enables_outbound_connections(self) -> None:
        restore = restrict_egress(5432, local_supplier_fixture=True)
        try:
            self.assertEqual(socket.getaddrinfo("example.org", 443)[0][4][0], "93.184.216.34")
            for host in ["www.example.org", "evil.example.org", "brave.com"]:
                with self.assertRaisesRegex(OSError, "QA_DNS_EGRESS_DENIED"):
                    socket.getaddrinfo(host, 443)
            with socket.socket() as client:
                with self.assertRaisesRegex(OSError, "QA_EGRESS_DENIED"):
                    client.connect(("93.184.216.34", 443))
                with self.assertRaisesRegex(OSError, "QA_EGRESS_DENIED"):
                    client.connect_ex(("93.184.216.34", 443))
        finally:
            restore()


if __name__ == "__main__":
    unittest.main()
