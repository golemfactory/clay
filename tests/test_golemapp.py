import sys

from click.testing import CliRunner
from mock import patch

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



    # @patch.object(startapp, 'start_app')
    # @patch('twisted.internet.reactor', create=True)
    # def test_start_gui(self, reactor, start_app):
    #     runner = CliRunner()
    #     runner.invoke(start, ['--datadir', self.path], catch_exceptions=False)
    #     assert start_app.called
    #     runner.invoke(start, ['--gui', '--datadir', self.path], catch_exceptions=False)
    #     assert start_app.called
    #
    # @patch('golemapp.OptNode')
    # @patch.object(startgui, 'start_gui')
    # @patch.object(sys, 'modules')
    # def test_start_node(self, modules, start_gui, node_class):
    #     runner = CliRunner()
    #     runner.invoke(start, ['--qt', '-r', '127.0.0.1:50000'], catch_exceptions=False)
    #     assert start_gui.called
    #
    # @patch.object(startapp, 'start_app')
    def test_patch_protocol_id(self, start_app):
        from golem.core.variables import PROTOCOL_ID
        runner = CliRunner()

        assert PROTOCOL_ID.P2P_ID == 15 \
               and PROTOCOL_ID.TASK_ID == 15

        runner.invoke(
            start, ['--protocol_id', 123456],
            catch_exceptions=False)

        assert start_app.called
        assert PROTOCOL_ID.P2P_ID == 123456 \
               and PROTOCOL_ID.TASK_ID == 123456
