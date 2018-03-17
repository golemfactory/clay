import os
from unittest.mock import patch

from OpenSSL import crypto

from golem.rpc.cert import CertificateManager
from golem.testutils import TempDirFixture


class TestCertificateManager(TempDirFixture):

    def test_init(self):
        cert_manager = CertificateManager(self.tempdir)
        assert not cert_manager.forward_secrecy
        assert cert_manager.key_path.startswith(self.tempdir)
        assert cert_manager.cert_path.startswith(self.tempdir)
        assert cert_manager.dh_path == ''

    def test_init_with_forward_secrecy(self):
        cert_manager = CertificateManager(self.tempdir,
                                          setup_forward_secrecy=True)
        assert cert_manager.forward_secrecy
        assert cert_manager.key_path.startswith(self.tempdir)
        assert cert_manager.cert_path.startswith(self.tempdir)
        assert cert_manager.dh_path.startswith(self.tempdir)

    @patch('golem.rpc.cert.crypto')
    @patch('golem.rpc.cert.CertificateManager._generate_dh_params')
    @patch('golem.rpc.cert.CertificateManager._generate_key_pair')
    @patch('golem.rpc.cert.CertificateManager._create_and_sign_certificate')
    def test_generate_if_needed(self, gen_dh_params, gen_key_pair, create_cert,
                                *_):

        cert_manager = CertificateManager(self.tempdir,
                                          setup_forward_secrecy=True)
        with patch('builtins.open'):
            cert_manager.generate_if_needed()

        assert gen_dh_params.called
        assert gen_key_pair.called
        assert create_cert.called

    def test_generate_dh_params(self):
        cert_manager = CertificateManager(self.tempdir,
                                          setup_forward_secrecy=True)
        cert_manager._generate_dh_params(cert_manager.dh_path, bits=16)

        with open(cert_manager.dh_path, 'rb') as f:
            assert f.read()

    def test_generate_key_pair(self):
        cert_manager = CertificateManager(self.tempdir)
        cert_manager._generate_key_pair(cert_manager.key_path, bits=64)
        assert isinstance(cert_manager.read_key(), crypto.PKey)

    def test_create_and_sign_certificate(self):
        cert_manager = CertificateManager(self.tempdir)
        cert_manager._generate_key_pair(cert_manager.key_path, bits=1024)

        key = cert_manager.read_key()
        cert_manager._create_and_sign_certificate(key, cert_manager.cert_path)
        assert cert_manager.read_certificate()
