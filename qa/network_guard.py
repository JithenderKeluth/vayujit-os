"""Test-process-only TCP egress guard, including Windows asyncio self-pipes."""

import socket
import threading
from _socket import socket as RawSocket
from collections.abc import Callable
from typing import Any


def restrict_egress(
    postgres_port: int, *, local_supplier_fixture: bool = False
) -> Callable[[], None]:
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_socketpair = socket.socketpair
    original_resolve = socket.getaddrinfo
    state = threading.local()

    def socketpair(
        family: int | None = None, type: int = socket.SOCK_STREAM, proto: int = 0
    ) -> tuple[socket.socket, socket.socket]:
        state.creating_pair = True
        try:
            # Preserve platform defaults: Windows' fallback rejects an explicit None.
            if family is None:
                return original_socketpair(type=type, proto=proto)
            return original_socketpair(family, type, proto)
        finally:
            state.creating_pair = False

    def allowed(address: Any) -> bool:
        postgres = isinstance(address, tuple) and address[:2] == ("127.0.0.1", postgres_port)
        self_pipe = (
            isinstance(address, tuple)
            and address[0] == "127.0.0.1"
            and getattr(state, "creating_pair", False)
        )
        return bool(postgres or self_pipe)

    def connect(sock: RawSocket, address: Any) -> None:
        if not allowed(address):
            raise OSError("QA_EGRESS_DENIED")
        original_connect(sock, address)

    def connect_ex(sock: RawSocket, address: Any) -> int:
        if not allowed(address):
            raise OSError("QA_EGRESS_DENIED")
        return original_connect_ex(sock, address)

    def resolve(host: Any, *args: Any, **kwargs: Any) -> Any:
        if local_supplier_fixture and host == "example.org":
            # Synthetic DNS input for the canonical LOCAL_FIXTURE URL validator only.
            # No resolver or socket is contacted; connect/connect_ex still deny this IP.
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        if host not in {None, "127.0.0.1", b"127.0.0.1", "localhost"}:
            raise OSError("QA_DNS_EGRESS_DENIED")
        return original_resolve(host, *args, **kwargs)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]
    socket.socketpair = socketpair
    socket.getaddrinfo = resolve

    def restore() -> None:
        socket.socket.connect = original_connect  # type: ignore[method-assign]
        socket.socket.connect_ex = original_connect_ex  # type: ignore[method-assign]
        socket.socketpair = original_socketpair
        socket.getaddrinfo = original_resolve

    return restore
