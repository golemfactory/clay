from pathlib import Path
from unittest import mock

import golem_task_api as api

from golem.apps.ssl import (
    create_golem_ssl_context,
    create_app_ssl_context_files,
    create_ssl_context_files,
    create_golem_ssl_context_files,
    generate_rsa_private_key,
    SSLContextConfig,
)
from golem.testutils import TempDirFixture


@mock.patch.object(SSLContextConfig, 'key_and_cert_directory', None)
class TestSslContext(TempDirFixture):

    def setUp(self):
        super().setUp()
        self.path = Path(self.path)

    def test_create_app_ssl_context_files(self):
        create_golem_ssl_context_files(self.path / 'sub')
        create_app_ssl_context_files(self.path / 'app')

        assert (self.path / 'app' / api.ssl.SERVER_KEY_FILE_NAME).exists()
        assert (self.path / 'app' / api.ssl.SERVER_CERT_FILE_NAME).exists()
        assert (self.path / 'app' / api.ssl.CLIENT_CERT_FILE_NAME).exists()

    def test_create_app_ssl_context_files_twice(self):
        create_golem_ssl_context_files(self.path / 'sub')

        to_patch = 'golem.apps.ssl.generate_rsa_private_key'
        with mock.patch(to_patch, wraps=generate_rsa_private_key) as mocked:
            create_app_ssl_context_files(self.path / 'app')
            create_app_ssl_context_files(self.path / 'app')

        assert mocked.call_count == 1

    def test_create_app_ssl_context_files_no_setup(self):
        with self.assertRaises(RuntimeError) as err:
            create_app_ssl_context_files(self.path / 'app')
        self._assert_context_not_set_up_exc(err.exception)

    def test_create_golem_ssl_context(self):
        create_golem_ssl_context_files(self.path / 'sub')
        create_app_ssl_context_files(self.path / 'sub_2')
        assert create_golem_ssl_context(self.path / 'sub_2')

    def test_create_golem_ssl_context_no_setup(self):
        with self.assertRaises(RuntimeError) as err:
            create_golem_ssl_context(self.path / 'sub')
        self._assert_context_not_set_up_exc(err.exception)

    def test_create_golem_ssl_context_missing_files(self):
        create_golem_ssl_context_files(self.path / 'sub')
        assert not create_golem_ssl_context(self.path / 'missing')

    def test_create_golem_ssl_context_missing_server_files(self):
        create_golem_ssl_context_files(self.path / 'sub')
        assert not create_golem_ssl_context(self.path / 'sub_2')

    @mock.patch(
        'golem.apps.ssl.generate_rsa_private_key',
        mock.Mock(side_effect=OSError))
    def test_create_ssl_context_files_exception(self):
        with self.assertRaises(OSError):
            create_ssl_context_files(
                self.path,
                'key_file',
                'cert_file',
                'test_label')

    @staticmethod
    def _assert_context_not_set_up_exc(exc: Exception):
        assert "context was not set up" in str(exc)
