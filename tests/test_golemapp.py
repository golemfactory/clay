import sys
import unittest.mock as mock

from click.testing import CliRunner

from golem.core.variables import PROTOCOL_CONST
from golem.testutils import TempDirFixture, PEP8MixIn
from golem.tools.ci import ci_skip
from golemapp import start


@ci_skip
class TestGolemApp(TempDirFixture, PEP8MixIn):
    PEP8_FILES = [
        "golemapp.py",
    ]

    @mock.patch('golemapp.Node')
    def test_start_node(self, node_class):
        runner = CliRunner()
        runner.invoke(start, ['--datadir', self.path], catch_exceptions=False)
        assert node_class.called

    def test_start_crossbar_worker(self):
        runner = CliRunner()
        args = ['--datadir', self.path, '-m', 'crossbar.worker.process']

        with mock.patch('crossbar.worker.process.run') as _run:
            with mock.patch.object(sys, 'argv', list(args)):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv

    def test_start_crossbar_worker_u(self):
        runner = CliRunner()
        args = ['--datadir', self.path, '-m', 'crossbar.worker.process', '-u']

        with mock.patch('crossbar.worker.process.run') as _run:
            with mock.patch.object(sys, 'argv', list(args)):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv
                assert '-u' not in sys.argv

    @mock.patch('golem.core.common.config_logging')
    @mock.patch('golemapp.Node')
    def test_patch_protocol_id(self, node_class, *_):
        runner = CliRunner()
        custom_id = '123456'

        # On testnet
        runner.invoke(
            start,
            ['--datadir', self.path, '--protocol_id', custom_id],
            catch_exceptions=False,
        )
        assert node_class.called
        node_class.reset_mock()
        assert PROTOCOL_CONST.ID == custom_id + '-testnet'

        # On mainnet
        runner.invoke(
            start,
            ['--datadir', self.path, '--protocol_id', custom_id, '--mainnet'],
            catch_exceptions=False,
        )
        assert node_class.called
        assert PROTOCOL_CONST.ID == custom_id

    @mock.patch('golem.rpc.cert.CertificateManager')
    def test_generate_rpc_cert(self, cert_manager, *_):
        cert_manager.return_value = cert_manager

        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path, '--generate-rpc-cert'],
            catch_exceptions=False,
        )
        assert cert_manager.generate_if_needed.called
