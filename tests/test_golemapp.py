import sys

from click.testing import CliRunner
from mock import patch

from golem.testutils import TempDirFixture
from golemapp import start


class TestGolemApp(TempDirFixture):

    @patch('golemapp.OptNode')
    def test_start_node(self, node_class):
        runner = CliRunner()
        runner.invoke(start, ['--nogui', '--datadir', self.path], catch_exceptions=False)
        assert node_class.called

    def test_start_crossbar_worker(self):
        runner = CliRunner()
        args = ['--nogui', '--datadir', self.path, '-m', 'crossbar.worker.process']

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

    def test_start_gui(self):
        runner = CliRunner()

        with patch('golemapp.start_app') as start_app:
            print runner.invoke(start, ['--datadir', self.path], catch_exceptions=False).output
            assert start_app.called

        with patch('golemapp.start_app') as start_app:
            runner.invoke(start, ['--gui', '--datadir', self.path], catch_exceptions=False)
            assert start_app.called
