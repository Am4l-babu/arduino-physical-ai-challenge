"""tools/gen_certs.py: the broker cert must validate for real network
addresses, not just localhost.

Found while wiring a real broker on the UNO Q: gen_certs.py's SAN only ever
included localhost/127.0.0.1, so a client connecting over the LAN (exactly
what a real ESP32 node does) failed hostname verification the moment it
wasn't on loopback relative to the broker.
"""

import pytest

pytest.importorskip("cryptography")
from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from tools.gen_certs import provision


def _san_values(cert):
    ext = cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
    return {str(v) for v in ext.get_values_for_type(x509.IPAddress)} | \
           set(ext.get_values_for_type(x509.DNSName))


def test_broker_cert_always_covers_localhost(tmp_path):
    out = provision(tmp_path, nodes=["fp1"])
    cert = x509.load_pem_x509_certificate((out / "broker.pem").read_bytes())
    sans = _san_values(cert)
    assert "127.0.0.1" in sans
    assert "localhost" in sans


def test_broker_cert_covers_a_real_lan_ip_when_asked(tmp_path):
    out = provision(tmp_path, nodes=["fp1"], broker_hosts=["192.168.1.5"])
    cert = x509.load_pem_x509_certificate((out / "broker.pem").read_bytes())
    sans = _san_values(cert)
    assert "192.168.1.5" in sans
    assert "127.0.0.1" in sans, "extra hosts must add to, not replace, the defaults"


def test_broker_cert_covers_a_hostname_too(tmp_path):
    out = provision(tmp_path, nodes=["fp1"], broker_hosts=["ikka.local"])
    cert = x509.load_pem_x509_certificate((out / "broker.pem").read_bytes())
    sans = _san_values(cert)
    assert "ikka.local" in sans


def test_client_certs_get_no_san_at_all(tmp_path):
    """Only the broker (server=True) needs a SAN; client identity certs are
    matched by CN, not hostname -- an extra_hosts leak onto a client cert
    would be a meaningless no-op at best, a confusing bug at worst."""
    out = provision(tmp_path, nodes=["fp1"], broker_hosts=["192.168.1.5"])
    cert = x509.load_pem_x509_certificate((out / "fp1.pem").read_bytes())
    with pytest.raises(x509.ExtensionNotFound):
        cert.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_ALTERNATIVE_NAME)
