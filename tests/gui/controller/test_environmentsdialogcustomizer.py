import unittest

from mock import MagicMock, Mock, patch
from twisted.internet.defer import Deferred

from gui.application import Gui
from gui.controller.environmentsdialogcustomizer import EnvironmentsDialogCustomizer
from gui.view.appmainwindow import AppMainWindow
from gui.view.dialog import EnvironmentsDialog
from gui.view.envtableelem import EnvTableElem


@patch('gui.view.dialog.Dialog.show')
class TestEnvironmentsDialogCustomizer(unittest.TestCase):

    def setUp(self):
        super(TestEnvironmentsDialogCustomizer, self).setUp()
        self.logic = MagicMock()
        self.gui = Gui(self.logic, AppMainWindow)
        self.gui.main_window.show = MagicMock()
        self.dialog = EnvironmentsDialog(self.gui.main_window.window)

        self.env_count = 3
        self.envs = [dict(
            id='ENVIRONMENT_{}'.format(i),
            supported=i % 2 == 0,
            description='description {}'.format(i),
            accepted=i % 2 == 0
        ) for i in range(self.env_count)]

        deferred = Deferred()
        deferred.callback(self.envs)

        self.logic.get_environments = Mock()
        self.logic.get_environments.return_value = deferred

    def tearDown(self):
        super(TestEnvironmentsDialogCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_load_data(self, *_):
        customizer = EnvironmentsDialogCustomizer(self.dialog, self.logic)
        assert customizer.gui.ui.tableWidget.rowCount() == self.env_count

    def test_task_table_row_clicked(self, *_):
        self.logic.disable_environment = Mock()
        self.logic.enable_environment = Mock()

        customizer = EnvironmentsDialogCustomizer(self.dialog, self.logic)
        customizer._setup_connections()

        click = customizer._EnvironmentsDialogCustomizer__task_table_row_clicked
        column = EnvTableElem.colItem.index('accept_tasks_item')

        click(90, -1)
        assert not self.logic.enable_environment.called
        assert not self.logic.disable_environment.called

        click(90, column)
        assert not self.logic.enable_environment.called
        assert not self.logic.disable_environment.called

        # no change in env dict
        click(0, column)
        assert not self.logic.enable_environment.called
        assert not self.logic.disable_environment.called

        self.envs[0]['accepted'] = False

        click(0, column)
        assert self.logic.enable_environment.called
        assert not self.logic.disable_environment.called

        self.logic.enable_environment.called = False
        self.logic.disable_environment.called = False

        self.envs[1]['accepted'] = True

        click(1, column)
        assert not self.logic.enable_environment.called
        assert self.logic.disable_environment.called

        self.logic.enable_environment.called = False
        self.logic.disable_environment.called = False

        # no change
        click(1, column)
        assert not self.logic.enable_environment.called
        assert self.logic.disable_environment.called
