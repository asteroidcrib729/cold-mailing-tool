"""Real loopback TLS/SMTP protocol; only this test enables sockets."""

import ipaddress
import socketserver
import ssl
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Thread

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from cold_mailer.domain.models import Outcome
from cold_mailer.infrastructure import smtp as mail_sender
from cold_mailer.infrastructure.smtp import SMTPTransport
from cold_mailer.settings import Settings
from tests.conftest import Rig

pytestmark = [pytest.mark.integration, pytest.mark.enable_socket]


class Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        server = self.server
        assert isinstance(server, TLSServer)
        with (
            server.tls.wrap_socket(self.request, server_side=True) as channel,
            channel.makefile("rwb") as stream,
        ):

            def reply(value: bytes) -> None:
                stream.write(value + b"\r\n")
                stream.flush()

            reply(b"220 localhost fixture")
            while line := stream.readline():
                command = line.split(b" ", 1)[0].strip().upper()
                if command == b"EHLO":
                    reply(b"250-localhost\r\n250 AUTH PLAIN")
                elif command == b"AUTH":
                    reply(b"235 authenticated")
                elif command == b"DATA":
                    reply(b"354 send message")
                    content = []
                    while (part := stream.readline()) not in (b".\r\n", b""):
                        content.append(part)
                    server.messages.append(b"".join(content))
                    reply(b"250 accepted")
                elif command == b"QUIT":
                    reply(b"221 bye")
                    return
                else:
                    reply(b"250 ok")


class TLSServer(socketserver.TCPServer):
    def __init__(self, context: ssl.SSLContext) -> None:
        self.tls = context
        self.messages: list[bytes] = []
        super().__init__(("127.0.0.1", 0), Handler)

    def handle_error(self, request: object, client_address: object) -> None:
        # Invalid client trust intentionally ends one handshake in the rejection case.
        return None


@pytest.mark.parametrize("trusted", [True, False])
def test_real_tls_and_envelope(
    rig: Rig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, trusted: bool
) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost fixture")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    cert_path, key_path = tmp_path / "fixture.crt", tmp_path / "fixture.key"
    cert_path.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_path, key_path)
    if trusted:
        client_context = ssl.create_default_context(cafile=str(cert_path))
        monkeypatch.setattr(mail_sender.ssl, "create_default_context", lambda: client_context)
    server = TLSServer(context)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        sender = replace(rig.sender, host="127.0.0.1", port=server.server_address[1], tls="tls")
        message = rig.message()
        result = SMTPTransport(Settings(tmp_path, network=True, timeout=3)).send(
            sender, "synthetic", message
        )
        assert result.outcome == (Outcome.ACCEPTED if trusted else Outcome.FAILED)
        assert len(server.messages) == int(trusted)
        if trusted:
            assert message.body.encode() in server.messages[0]
            assert message.message_id.encode() in server.messages[0]
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
