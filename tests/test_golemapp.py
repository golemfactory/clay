from click.testing import CliRunner
import sys
import unittest.mock as mock

from golem.testutils import TempDirFixture
from golem.tools.ci import ci_skip
from golemapp import start

from gui import startapp, startgui


class TestGolemApp(TempDirFixture):
    @ci_skip
    @mock.patch('golemapp.OptNode')
    def test_start_node(self, node_class):
        runner = CliRunner()
        runner.invoke(start, ['--nogui', '--datadir', self.path], catch_exceptions=False)
        assert node_class.called

    @ci_skip
    def test_start_crossbar_worker(self):
        runner = CliRunner()
        args = ['--nogui', '--datadir', self.path, '-m', 'crossbar.worker.process']

        with mock.patch('crossbar.worker.process.run') as _run:
            with mock.patch.object(sys, 'argv', list(args)):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv

        with mock.patch('crossbar.worker.process.run') as _run:
            with mock.patch.object(sys, 'argv', list(args) + ['-u']):
                runner.invoke(start, sys.argv, catch_exceptions=False)
                assert _run.called
                assert '-m' not in sys.argv
                assert '-u' not in sys.argv

    def setUp(self):
        super(TestGolemApp, self).setUp()

    def tearDown(self):
        super(TestGolemApp, self).tearDown()

    @ci_skip
    @mock.patch('golemapp.install_reactor')
    @mock.patch.object(startapp, 'start_app')
    def test_start_gui(self, start_app, *_):
        runner = CliRunner()
        runner.invoke(start, ['--datadir', self.path], catch_exceptions=False)
        assert start_app.called
        runner.invoke(start, ['--gui', '--datadir', self.path], catch_exceptions=False)
        assert start_app.called

    @ci_skip
    @mock.patch('golemapp.OptNode')
    @mock.patch.object(startgui, 'start_gui')
    @mock.patch.object(sys, 'modules')
    def test_start_node(self, modules, start_gui, node_class):
        runner = CliRunner()
        runner.invoke(start, ['--qt', '-r', '127.0.0.1:50000'], catch_exceptions=False)
        assert start_gui.called
