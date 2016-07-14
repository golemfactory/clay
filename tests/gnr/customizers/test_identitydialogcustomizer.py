from unittest import TestCase

from gnr.ui.appmainwindow import AppMainWindow

from gnr.application import GNRGui
from mock import Mock
from twisted.internet.defer import Deferred

from gnr.customizers.identitydialogcustomizer import IdentityDialogCustomizer, SaveKeysDialogCustomizer
from gnr.ui.dialog import IdentityDialog, SaveKeysDialog
from golem.tools.testwithreactor import TestWithReactor


class TestIdentityDialogCustomizer(TestCase):

    def test(self):
        logic = Mock()

        gnrgui = GNRGui(logic, AppMainWindow)
        gnrgui.show = Mock()
        gnrgui.main_window.show = Mock()

        identity_dialog = IdentityDialog(gnrgui.main_window.window)
        customizer = IdentityDialogCustomizer(identity_dialog, logic)
        customizer.keys_auth = Mock()
        customizer._generate_keys(difficulty=1)

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()


class TestSaveKeysDialogCustomizer(TestWithReactor):

    def test(self):
        logic = Mock()

        gnrgui = GNRGui(logic, AppMainWindow)
        gnrgui.show = Mock()
        gnrgui.main_window.show = Mock()

        dialog = SaveKeysDialog(gnrgui.main_window.window)
        customizer = SaveKeysDialogCustomizer(dialog, logic)

        d = Deferred()
        d.result = False
        d.called = True

        logic.save_keys_to_files.return_value = d
        dialog.window.close = Mock()

        customizer._save_keys()
        assert not dialog.window.close.called

        d.result = True

        customizer._save_keys()
        assert dialog.window.close.called

        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()
