import gc
import logging
from pathlib import Path
from typing import Union

import enum
import secrets

from ipaddress import IPv4Address

from golem.crypto import (
    generate_dh_parameters,
    generate_rsa_private_key,
    generate_x509_certificate,
    load_rsa_private_key,
    load_x509_certificate,
    save_dh_parameters,
    save_rsa_private_key,
    save_x509_certificate,
)

logger = logging.getLogger(__name__)


DH_PARAM_BITS = 2048
DH_PARAM_BITS_LOW = 1024
KEY_BITS = 2048


class CertificateError(Exception):
    pass


class CertificateManager:

    DH_FILE_NAME = "rpc_dh_param.pem"
    PRIVATE_KEY_FILE_NAME = "rpc_key.pem"
    CERTIFICATE_FILE_NAME = "rpc_cert.pem"

    @enum.unique
    class CrossbarUsers(enum.Enum):
        golemcli = enum.auto()
        electron = enum.auto()
        golemapp = enum.auto()
        docker = enum.auto()

    SECRET_EXT = "tck"
    SECRETS_DIR = "secrets"
    SECRET_LENGTH = 128

    def __init__(
            self,
            dest_dir: Union[str, Path],
            setup_forward_secrecy: bool = False,
    ) -> None:
        dest_dir = Path(dest_dir)
        self.forward_secrecy = setup_forward_secrecy
        self.key_path = dest_dir / self.PRIVATE_KEY_FILE_NAME
        self.cert_path = dest_dir / self.CERTIFICATE_FILE_NAME
        self.dh_path = dest_dir / self.DH_FILE_NAME
        self.secrets_path = dest_dir / self.SECRETS_DIR

        self.secrets_path.mkdir(parents=True, exist_ok=True)

    def generate_if_needed(self):
        if not self.dh_path.exists():
            if self.forward_secrecy:
                dh_param_bits = DH_PARAM_BITS
            else:  # required to generate for Windows
                dh_param_bits = DH_PARAM_BITS_LOW

            logger.info("Generating DH parameters: %r", self.dh_path)
            save_dh_parameters(
                self.dh_path,
                generate_dh_parameters(dh_param_bits))

        if not self.key_path.exists():
            logger.info("Generating RSA private key: %r", self.key_path)
            save_rsa_private_key(
                self.key_path,
                generate_rsa_private_key())

        if not self.cert_path.exists():
            logger.info("Generating X509 certificate: %r", self.cert_path)
            key = load_rsa_private_key(self.key_path)
            save_x509_certificate(
                self.cert_path,
                generate_x509_certificate(
                    key,
                    names=['localhost'],
                    ip_addresses=[IPv4Address('127.0.0.1')]))
            logger.info('RPC self-signed certificate has been created')

        self.generate_secrets()
        gc.collect()

    def generate_secrets(self):
        paths = [
            self.secrets_path / f"{p}.{self.SECRET_EXT}"
            for p in self.CrossbarUsers.__members__.keys()
        ]

        for path in paths:
            if not path.exists():
                secret = secrets.token_hex(self.SECRET_LENGTH)
                path.write_text(secret, encoding='utf-8')

    def get_secret(self, p: 'CertificateManager.CrossbarUsers') -> str:
        path = self.secrets_path / f"{p.name}.{self.SECRET_EXT}"
        if not path.is_file():
            raise CertificateError(
                f"No secret for `{p.name}` in `{path}`. "
                f"Please ensure you're using the correct Golem data directory."
            )
        return path.read_text('utf-8')

    def read_certificate(self) -> bytes:
        return load_x509_certificate(self.cert_path)
