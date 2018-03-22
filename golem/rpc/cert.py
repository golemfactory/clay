import logging

import os
import random

from OpenSSL import crypto
from OpenSSL._util import ffi, lib

from golem.core.common import is_windows
from golem.rpc.common import X509_COMMON_NAME

logger = logging.getLogger(__name__)


DH_PARAM_BITS = 2048
DH_PARAM_BITS_LOW = 1024
KEY_BITS = 2048


class CertificateManager:

    DH_FILE_NAME = "rpc_dh_param.pem"
    PRIVATE_KEY_FILE_NAME = "rpc_key.pem"
    CERTIFICATE_FILE_NAME = "rpc_cert.pem"

    def __init__(self, dest_dir, setup_forward_secrecy=False):
        self.forward_secrecy = setup_forward_secrecy
        self.use_dh_params = self.forward_secrecy or is_windows()

        self.key_path = os.path.join(dest_dir, self.PRIVATE_KEY_FILE_NAME)
        self.cert_path = os.path.join(dest_dir, self.CERTIFICATE_FILE_NAME)

        if self.use_dh_params:
            self.dh_path = os.path.join(dest_dir, self.DH_FILE_NAME)
        else:
            self.dh_path = ''

    def generate_if_needed(self):
        if self.use_dh_params and not os.path.exists(self.dh_path):

            if self.forward_secrecy:
                dh_param_bits = DH_PARAM_BITS
            else:  # required to generate for Windows
                dh_param_bits = DH_PARAM_BITS_LOW

            self._generate_dh_params(self.dh_path, dh_param_bits)

        if not os.path.exists(self.key_path):
            self._generate_key_pair(self.key_path)

        if not os.path.exists(self.cert_path):
            key = self.read_key()
            self._create_and_sign_certificate(key, self.cert_path)
            del key

        import gc
        gc.collect()

    def read_key(self) -> crypto.PKey:
        with open(self.key_path, 'r') as key_file:
            buffer = key_file.read()
            try:
                return crypto.load_privatekey(crypto.FILETYPE_PEM, buffer)
            finally:
                del buffer

    def read_certificate(self) -> bytes:
        with open(self.cert_path, "rb") as cert_file:
            return cert_file.read()

    @staticmethod
    def _generate_dh_params(output_path: str, bits: int) -> None:
        # pylint: disable=no-member
        logger.info("Generating DH key exchange params: %r", output_path)

        dh = lib.DH_new()
        lib.DH_generate_parameters_ex(dh, bits, 2, ffi.NULL)
        with open(output_path, 'w') as output_file:
            lib.DHparams_print_fp(output_file, dh)
        lib.DH_free(dh)

    @staticmethod
    def _generate_key_pair(output_path: str, bits: int = KEY_BITS) -> None:
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

        """
        Creates a self signed certificate for personal use. Lifetime of the
        certificate spans from epoch to now + 10 years (an arbitrarily big
        number), in order not to bother with expiring certificates. This
        certificate may be regenerated at will, and should only serve a single
        purpose (e.g. WSS communication).

        :param key: private key
        :param output_path: output path
        :param entity: certificate subject parameters
        :return:
        """

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

    @staticmethod
    def _apply_to_subject(cert_subject, **entity):
        cert_subject.C = entity.pop('C', 'CH')
        cert_subject.ST = entity.pop('ST', '-')
        cert_subject.L = entity.pop('L', '-')
        cert_subject.O = entity.pop('O', '-')  # noqa
        cert_subject.OU = entity.pop('OU', '-')
        cert_subject.CN = entity.pop('CN', X509_COMMON_NAME)
        cert_subject.CN = entity.pop('SAN', X509_COMMON_NAME)
