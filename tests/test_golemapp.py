import sys
import unittest.mock as mock

from click.testing import CliRunner
from portalocker import LockException

from golem.rpc import WORKER_PROCESS_STANDALONE_ARGS
from golem.testutils import TempDirFixture, PEP8MixIn
from golem.tools.ci import ci_skip
from golemapp import start, main, start_crossbar_worker
from tests.golem.config.utils import mock_config


@ci_skip
@mock.patch('twisted.internet.asyncioreactor', mock.Mock(), create=True)
@mock.patch('twisted.internet.reactor', mock.Mock(), create=True)
class TestGolemApp(TempDirFixture, PEP8MixIn):
    PEP8_FILES = [
        "golemapp.py",
    ]

    @mock.patch('golem.node.Node')
    def test_start_node(self, node_class, *_):
        runner = CliRunner()
        runner.invoke(start, ['--datadir', self.path], catch_exceptions=False)
        assert node_class.called

    def test_start_crossbar_worker(self):
        args = ['--datadir', self.path] + WORKER_PROCESS_STANDALONE_ARGS

        with mock.patch('golemapp.start') as run_start:
            with mock.patch('golemapp.start_crossbar_worker') as run_start_cbar:
                with mock.patch.object(sys, 'argv', args):
                    main()
                    assert not run_start.called
                    assert run_start_cbar.called

    def test_start_crossbar_worker_u(self, *_):
        runner = CliRunner()
        args = ['--datadir', self.path, '-u'] + WORKER_PROCESS_STANDALONE_ARGS

        with mock.patch('runpy.run_module'):
            with mock.patch.object(sys, 'argv', list(args)):
                runner.invoke(start_crossbar_worker, args,
                              catch_exceptions=False)
                assert all(a not in sys.argv for a in
                           WORKER_PROCESS_STANDALONE_ARGS)
                assert '-u' not in sys.argv

    @mock.patch('golem.core.common.config_logging')
    @mock.patch('golem.appconfig.AppConfig')
    @mock.patch('golem.node.Node')
    def test_patch_protocol_id(self, node_class, *_):
        runner = CliRunner()
        custom_id = '123456'

        # On testnet
        with mock_config():
            runner.invoke(start, ['--datadir', self.path,
                                  '--protocol_id', custom_id],
                          catch_exceptions=False,)
            assert node_class.called
            node_class.reset_mock()

            from golem.core.variables import PROTOCOL_CONST
            assert PROTOCOL_CONST.ID == custom_id + '-testnet'

        # On mainnet
        with mock_config():
            runner.invoke(start, ['--datadir', self.path,
                                  '--protocol_id', custom_id,
                                  '--mainnet'],
                          catch_exceptions=False,)
            assert node_class.called

            from golem.core.variables import PROTOCOL_CONST
            assert PROTOCOL_CONST.ID == custom_id

    @mock.patch('golem.rpc.cert.CertificateManager')
    def test_generate_rpc_cert(self, cert_manager, *_):
        cert_manager.return_value = cert_manager

        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path],
            catch_exceptions=False,
        )
        assert cert_manager.generate_if_needed.called

    @mock.patch('golem.node.Node')
    def test_accept_terms(self, node_cls, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path, '--accept-terms'],
            catch_exceptions=False
        )
        node_cls().accept_terms.assert_called_once_with()

    @mock.patch('golem.node.Node')
    def test_accept_concent_terms(self, node_cls, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path, '--accept-concent-terms'],
            catch_exceptions=False
        )
        node_cls().accept_concent_terms.assert_called_once_with()

    @mock.patch('golem.node.Node')
    def test_accept_all_terms(self, node_cls, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path, '--accept-all-terms'],
            catch_exceptions=False
        )
        node_cls().accept_terms.assert_called_once_with()
        node_cls().accept_concent_terms.assert_called_once_with()

    @mock.patch('golem.node.Node')
    @mock.patch('portalocker.Lock.acquire')
    def test_datadir_lock_success(self, lock, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path],
            catch_exceptions=False,
        )

        assert lock.called

    @mock.patch('golem.node.Node')
    @mock.patch('portalocker.Lock.acquire', side_effect=LockException)
    @mock.patch('golemapp.logger')
    def test_datadir_lock_failure(self, logger, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path],
            catch_exceptions=False,
        )

        args, _kwargs = logger.error.call_args
        assert self.path in args[0]

    @mock.patch('golem.node.Node')
    def test_node_start_called(self, node_cls, *_):
        runner = CliRunner()
        runner.invoke(
            start,
            ['--datadir', self.path, '--accept-terms'],
            catch_exceptions=False
        )
        node_cls().start.assert_called_once()
