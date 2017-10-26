import sys

from click.testing import CliRunner
from mock import patch

from golem.core.variables import PROTOCOL_ID
from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golemapp import start


@ci_skip
class TestGolemApp(TempDirFixture):
    def setUp(self):
        super(TestGolemApp, self).setUp()

    def tearDown(self):
        super(TestGolemApp, self).tearDown()

    @patch('golemapp.OptNode')
    def test_start_node(self, node_class):
        runner = CliRunner()
        runner.invoke(start, ['--datadir', self.path], catch_exceptions=False)
        assert node_class.called

    def test_start_crossbar_worker(self):
        runner = CliRunner()
        args = ['--datadir', self.path, '-m', 'crossbar.worker.process']

        with patch('crossbar.worker.process.run') as _run:
            with patch.object(sys, 'argv', list(args)):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv

        with patch('crossbar.worker.process.run') as _run:
            with patch.object(sys, 'argv', list(args) + ['-u']):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv
                assert '-u' not in sys.argv

    @patch('golem.core.common.config_logging')
    @patch('golemapp.OptNode')
    def test_patch_protocol_id(self, node_class, *_):
        runner = CliRunner()

        assert PROTOCOL_ID.P2P_ID == 15 \
               and PROTOCOL_ID.TASK_ID == 16

        runner.invoke(start,
                      ['--datadir', self.path]
                      + ['--protocol_id', 123456],
                      catch_exceptions=False)

        assert node_class.called
        assert PROTOCOL_ID.P2P_ID == 123456 \
               and PROTOCOL_ID.TASK_ID == 123456
