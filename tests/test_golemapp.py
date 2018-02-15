import sys

from click.testing import CliRunner
from mock import patch

from golem.core.variables import PROTOCOL_CONST
from golem.testutils import TempDirFixture, PEP8MixIn
from golem.tools.ci import ci_skip
from golemapp import start


@ci_skip
class TestGolemApp(TempDirFixture, PEP8MixIn):
    PEP8_FILES = [
        "golemapp.py",
    ]

    @patch('golemapp.Node')
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
    @patch('golemapp.Node')
    def test_patch_protocol_id(self, node_class, *_):
        runner = CliRunner()

        custom_id = 123456

        runner.invoke(start,
                      ['--datadir', self.path, '--protocol_id', custom_id],
                      catch_exceptions=False)

        assert node_class.called
        assert PROTOCOL_CONST.ID == custom_id
