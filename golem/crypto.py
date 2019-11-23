import ipaddress
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional, Union

from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dh, rsa

RSA_PRIVATE_KEY_FILE_NAME = 'key.pem'
RSA_PUBLIC_EXPONENT = 65537
RSA_KEY_SIZE = 2048

DH_PARAMS_FILE_NAME = 'dh.der'
DH_KEY_SIZE = 2048

X509_CERT_FILE_NAME = 'x509.pem'
X509_COMMON_NAME = 'golem.local'
X509_LIFETIME = timedelta(days=10 * 365)
X509_SERIAL_NUMBER = 9013

IpAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]


def generate_rsa_private_key(
        public_exponent: int = RSA_PUBLIC_EXPONENT,
        key_size: int = RSA_KEY_SIZE,
) -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(
        public_exponent=public_exponent,
        key_size=key_size,
        backend=default_backend(),
    )


def generate_dh_parameters(
        key_size: int = DH_KEY_SIZE,
) -> dh.DHParameters:
    return dh.generate_parameters(
        generator=2,
        key_size=key_size,
        backend=default_backend())


def generate_x509_certificate(
        key: rsa.RSAPrivateKey,
        names: Optional[Iterable[str]] = None,
        ip_addresses: Optional[Iterable[IpAddress]] = None,
) -> x509.Certificate:
    constraints = x509.BasicConstraints(
        ca=True,  # CA cert
        path_length=0)  # disallow creating chains

    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, X509_COMMON_NAME)
    ])

    subject_alt_names = [x509.DNSName(X509_COMMON_NAME)]
    for alt_name in names or []:
        subject_alt_names.append(x509.DNSName(str(alt_name)))
    for addr in ip_addresses or []:
        subject_alt_names.append(x509.IPAddress(ipaddress.ip_address(addr)))

    san = x509.SubjectAlternativeName(subject_alt_names)
    now = datetime.utcnow()
    return (
        x509.CertificateBuilder()
        .public_key(key.public_key())
        .subject_name(name)
        .issuer_name(name)
        .serial_number(X509_SERIAL_NUMBER)
        .not_valid_before(now)
        .not_valid_after(now + X509_LIFETIME)
        .add_extension(san, False)
        .add_extension(constraints, False)
        .sign(
            key,
            hashes.SHA256(),
            default_backend())
    )


def load_rsa_private_key(
        path: Path
) -> rsa.RSAPrivateKey:
    return serialization.load_pem_private_key(
        path.read_bytes(),
        password=None,
        backend=default_backend()
    )


def load_dh_parameters(
        path: Path,
) -> dh.DHParameters:
    return serialization.load_der_parameters(
        path.read_bytes(),
        backend=default_backend()
    )


def load_x509_certificate(
        path: Path,
) -> bytes:
    return path.read_bytes()


def save_rsa_private_key(
        path: Path,
        key: rsa.RSAPrivateKey,
) -> None:
    key_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption())

    path.write_bytes(key_pem)


def save_dh_parameters(
        path: Path,
        parameters: dh.DHParameters,
) -> None:
    parameters_der = parameters.parameter_bytes(
        serialization.Encoding.DER,
        serialization.ParameterFormat.PKCS3)

    path.write_bytes(parameters_der)


def save_x509_certificate(
        path: Path,
        cert: x509.Certificate,
) -> None:
    cert_pem = cert.public_bytes(
        encoding=serialization.Encoding.PEM)

    path.write_bytes(cert_pem)
