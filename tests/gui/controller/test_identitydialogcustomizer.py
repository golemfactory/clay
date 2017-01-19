import time

from mock import Mock, patch
from twisted.internet.defer import Deferred

from golem.testutils import TempDirFixture
from golem.tools.testwithreactor import TestWithReactor

from gui.application import Gui
from gui.controller.identitydialogcustomizer import IdentityDialogCustomizer, SaveKeysDialogCustomizer
from gui.view.appmainwindow import AppMainWindow
from gui.view.dialog import IdentityDialog, SaveKeysDialog


class TestIdentityDialogCustomizer(TempDirFixture):

    def setUp(self):
        super(TestIdentityDialogCustomizer, self).setUp()
        self.logic = Mock()
        self.gui = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gui.app.exit(0)
        self.gui.app.deleteLater()
        super(TestIdentityDialogCustomizer, self).tearDown()

    @patch('gui.view.dialog.GeneratingKeyWindow.show')
    def test(self, *_):
        self.gui.show = Mock()
        self.gui.main_window.show = Mock()

        identity_dialog = IdentityDialog(self.gui.main_window.window)
        identity_dialog.window.show = Mock()
        customizer = IdentityDialogCustomizer(identity_dialog, self.logic)
        customizer.keys_auth = Mock()
        customizer._generate_keys(difficulty=1)


class TestSaveKeysDialogCustomizer(TestWithReactor):

    def setUp(self):
        super(TestSaveKeysDialogCustomizer, self).setUp()
        self.logic = Mock()
        self.gui = Gui(Mock(), AppMainWindow)

    def tearDown(self):
        self.gui.app.exit(0)
        self.gui.app.deleteLater()
        super(TestSaveKeysDialogCustomizer, self).tearDown()

    def test(self):
        self.gui.main_window.show = Mock()

        dialog = SaveKeysDialog(self.gui.main_window.window)
        dialog.window.show = Mock()
        dialog.window.close = Mock()
        customizer = SaveKeysDialogCustomizer(dialog, self.logic)
        customizer.show_error_window = Mock()

        d = Deferred()
        d.result = False
        d.called = True

        self.logic.save_keys_to_files.return_value = d
        dialog.window.close = Mock()

        customizer._save_keys()
        time.sleep(0.1)
        assert not dialog.window.close.called

        d.result = True

        customizer._save_keys()
        time.sleep(0.1)
        assert dialog.window.close.called
