"""Provision the DOMORA PKI: one house CA, a broker cert, per-node client certs.

Per spec §17: mTLS on MQTT with per-node client certificates, and the cert
CN doubles as the broker username so ACLs can confine each node to its own
topic namespace — a stolen node's cert is a contained blast radius.

    python -m tools.gen_certs --out certs --nodes fp1 fp2 env1 perc1

Produces:  ca.pem  broker.pem/.key  hub.pem/.key  <node>.pem/.key ...
The CA key stays on the commissioning machine; nodes get only their own
keypair + ca.pem.
"""

import argparse
import datetime
import ipaddress
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

VALID_DAYS = 3650


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _name(cn: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _builder(subject_cn: str, issuer_cn: str, public_key):
    now = datetime.datetime.now(datetime.timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(_name(subject_cn))
        .issuer_name(_name(issuer_cn))
        .public_key(public_key)
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=VALID_DAYS))
    )


def make_ca():
    key = _key()
    cert = (
        _builder("domora-ca", "domora-ca", key.public_key())
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_cert(cn: str, ca_key, ca_cert, server: bool = False):
    key = _key()
    builder = (
        _builder(cn, "domora-ca", key.public_key())
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.ExtendedKeyUsage(
                [ExtendedKeyUsageOID.SERVER_AUTH if server else ExtendedKeyUsageOID.CLIENT_AUTH]
            ),
            critical=False,
        )
    )
    if server:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]
            ),
            critical=False,
        )
    cert = builder.sign(ca_key, hashes.SHA256())
    return key, cert


def _write(out: Path, name: str, key, cert) -> None:
    (out / f"{name}.key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    (out / f"{name}.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))


def provision(out_dir, nodes) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ca_key, ca_cert = make_ca()
    _write(out, "ca", ca_key, ca_cert)

    broker_key, broker_cert = make_cert("broker", ca_key, ca_cert, server=True)
    _write(out, "broker", broker_key, broker_cert)
    for identity in ["hub", *nodes]:
        key, cert = make_cert(identity, ca_key, ca_cert)
        _write(out, identity, key, cert)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Provision the DOMORA mTLS PKI")
    parser.add_argument("--out", default="certs")
    parser.add_argument("--nodes", nargs="+", default=["fp1", "fp2", "env1"])
    args = parser.parse_args()
    out = provision(args.out, args.nodes)
    print(f"PKI written to {out.resolve()} (identities: hub, {', '.join(args.nodes)})")


if __name__ == "__main__":
    main()
