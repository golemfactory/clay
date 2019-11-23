from unittest.mock import patch, Mock

from golem.rpc.cert import CertificateManager
from golem.testutils import TempDirFixture


class TestGenerateArtifacts(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.cert_manager = CertificateManager(self.tempdir)

    @patch('golem.rpc.cert.DH_PARAM_BITS', 512)
    @patch('golem.crypto.RSA_KEY_SIZE', 1024)
    @patch('golem.crypto.DH_KEY_SIZE', 1024)
    def test_generate_if_needed(self):
        cert_manager = self.cert_manager
        cert_manager.generate_if_needed()

        key = cert_manager.key_path.read_bytes()
        cert = cert_manager.cert_path.read_bytes()
        dh = cert_manager.dh_path.read_bytes()

        assert key
        assert cert
        assert dh

        cert_manager.generate_if_needed()

        assert key == cert_manager.key_path.read_bytes()
        assert cert == cert_manager.cert_path.read_bytes()
        assert dh == cert_manager.dh_path.read_bytes()

    def test_generate_secrets(self):
        cert_manager = self.cert_manager
        cert_manager.generate_secrets()

        generated_names = set(map(
            lambda p: p.name,
            cert_manager.secrets_path.iterdir()))
        expected_names = set(
            f"{x}.{cert_manager.SECRET_EXT}"
            for x in cert_manager.CrossbarUsers.__members__.keys())

        assert generated_names == expected_names

    @patch("secrets.token_hex", Mock(return_value="secret"))
    def test_get_secret(self):
        cert_manager = self.cert_manager
        cert_manager.generate_secrets()

        assert all(
            cert_manager.get_secret(x) == "secret"
            for x in cert_manager.CrossbarUsers.__members__.values())
