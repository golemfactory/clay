import logging

import os
import random

from OpenSSL import crypto
from OpenSSL._util import ffi, lib

from golem.rpc.common import X509_COMMON_NAME

logger = logging.getLogger(__name__)


class CertificateManager:

    DH_FILE_NAME = "rpc_dh_param.pem"
    PRIVATE_KEY_FILE_NAME = "rpc_key.pem"
    CERTIFICATE_FILE_NAME = "rpc_cert.pem"

    def __init__(self, dest_dir, setup_forward_secrecy=False):
        self.forward_secrecy = setup_forward_secrecy
        self.key_path = os.path.join(dest_dir, self.PRIVATE_KEY_FILE_NAME)
        self.cert_path = os.path.join(dest_dir, self.CERTIFICATE_FILE_NAME)

        if self.forward_secrecy:
            self.dh_path = os.path.join(dest_dir, self.DH_FILE_NAME)
        else:
            self.dh_path = ''

    def generate_if_needed(self):
        if self.forward_secrecy and not os.path.exists(self.dh_path):
            self._generate_dh_params(self.dh_path)

        if not os.path.exists(self.key_path):
            self._generate_key_pair(self.key_path)

        if not os.path.exists(self.cert_path):
            with open(self.key_path, 'r') as key_file:
                buffer = key_file.read()

            key = crypto.load_privatekey(crypto.FILETYPE_PEM, buffer)
            self._create_and_sign_certificate(key, self.cert_path)
            del key, buffer

        import gc
        gc.collect()

    def read_certificate(self) -> bytes:
        with open(self.cert_path, "rb") as cert_file:
            return cert_file.read()

    @staticmethod
    def _generate_dh_params(output_path: str, bits: int = 2048) -> None:
        logger.info("Generating DH key exchange params: %r", output_path)

        dh = lib.DH_new()
        lib.DH_generate_parameters_ex(dh, bits, 2, ffi.NULL)
        with open(output_path, 'w') as output_file:
            lib.DHparams_print_fp(output_file, dh)
        lib.DH_free(dh)

    @staticmethod
    def _generate_key_pair(output_path: str, bits: int = 2048) -> None:
        logger.info("Creating an RSA key pair: %r", output_path)

        key = crypto.PKey()
        key.generate_key(crypto.TYPE_RSA, bits)

        with open(output_path, "wb") as key_file:
            buffer = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
            key_file.write(buffer)
        del key, buffer

    @classmethod
    def _create_and_sign_certificate(cls, key: crypto.PKey, output_path: str,
                                     **entity):

        logger.info("Creating a self-signed certificate: %r", output_path)

        cert = crypto.X509()
        cert_subject = cert.get_subject()

        cls._apply_to_subject(cert_subject, **entity)

        cert.set_serial_number(random.randint(0, 10 * 10 ** 18))
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)

        cert.set_issuer(cert_subject)
        cert.set_pubkey(key)
        cert.sign(key, 'sha1')

        with open(output_path, "wb") as cert_file:
            buffer = crypto.dump_certificate(crypto.FILETYPE_PEM, cert)
            cert_file.write(buffer)
        del cert

    @classmethod
    def _apply_to_subject(cls, cert_subject, **entity):
        cert_subject.C = entity.pop('C', 'CH')
        cert_subject.ST = entity.pop('ST', '-')
        cert_subject.L = entity.pop('L', '-')
        cert_subject.O = entity.pop('O', '-')
        cert_subject.OU = entity.pop('OU', '-')
        cert_subject.CN = entity.pop('CN', X509_COMMON_NAME)
