
import time

from golem.testutils import TempDirFixture

from gnr.ui.appmainwindow import AppMainWindow

from gui.application import GNRGui
from mock import Mock, patch
from twisted.internet.defer import Deferred

from gnr.customizers.identitydialogcustomizer import IdentityDialogCustomizer, SaveKeysDialogCustomizer
from gnr.ui.dialog import IdentityDialog, SaveKeysDialog
from golem.tools.testwithreactor import TestWithReactor


class TestIdentityDialogCustomizer(TempDirFixture):

    def setUp(self):
        super(TestIdentityDialogCustomizer, self).setUp()
        self.logic = Mock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()
        super(TestIdentityDialogCustomizer, self).tearDown()

    @patch('gnr.ui.dialog.GeneratingKeyWindow.show')
    def test(self, *_):
        self.gnrgui.show = Mock()
        self.gnrgui.main_window.show = Mock()

        identity_dialog = IdentityDialog(self.gnrgui.main_window.window)
        identity_dialog.window.show = Mock()
        customizer = IdentityDialogCustomizer(identity_dialog, self.logic)
        customizer.keys_auth = Mock()
        customizer._generate_keys(difficulty=1)


class TestSaveKeysDialogCustomizer(TestWithReactor):

    def setUp(self):
        super(TestSaveKeysDialogCustomizer, self).setUp()
        self.logic = Mock()
        self.gnrgui = GNRGui(Mock(), AppMainWindow)

    def tearDown(self):
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()
        super(TestSaveKeysDialogCustomizer, self).tearDown()

    def test(self):
        self.gnrgui.main_window.show = Mock()

        dialog = SaveKeysDialog(self.gnrgui.main_window.window)
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
