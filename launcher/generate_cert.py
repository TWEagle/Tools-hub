from __future__ import annotations

from pathlib import Path
from typing import Iterable
import ipaddress
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_localhost_cert(
    *,
    cert_path: Path,
    key_path: Path,
    common_name: str = "localhost",
    dns_names: Iterable[str] = ("localhost",),
    ip_addrs: Iterable[str] = ("127.0.0.1", "::1"),
    days: int = 3650,
) -> None:
    cert_path.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])

    san_items = []
    for d in dns_names:
        try:
            san_items.append(x509.DNSName(str(d)))
        except Exception:
            pass
    for ip in ip_addrs:
        try:
            san_items.append(x509.IPAddress(ipaddress.ip_address(str(ip))))
        except Exception:
            pass

    now = datetime.now(timezone.utc)

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=int(days)))
        .add_extension(x509.SubjectAlternativeName(san_items), critical=False)
        .sign(key, hashes.SHA256())
    )

    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
