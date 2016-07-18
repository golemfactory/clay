from unittest import TestCase

from PyQt4.QtCore import Qt
from PyQt4.QtTest import QTest
from mock import MagicMock

from gnr.application import GNRGui
from gnr.customizers.gnrmainwindowcustomizer import GNRMainWindowCustomizer
from gnr.ui.appmainwindow import AppMainWindow


class TestGNRMainWindowCustomizer(TestCase):
    def test_description(self):
        gnrgui = GNRGui(MagicMock(), AppMainWindow)
        customizer = GNRMainWindowCustomizer(gnrgui.get_main_window(), MagicMock())
        assert isinstance(customizer, GNRMainWindowCustomizer)
        customizer.set_options(MagicMock(), "ID1", "ETH_ADDR1", "DESC1")
        assert customizer.gui.ui.descriptionTextEdit.toPlainText() == "DESC1"
        customizer.set_options(MagicMock(), "ID1", "ETH_ADDR1", "DESC2")
        assert customizer.gui.ui.descriptionTextEdit.toPlainText() == "DESC2"
        assert customizer.gui.ui.editDescriptionButton.isEnabled()
        assert not customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert not customizer.gui.ui.descriptionTextEdit.isEnabled()

        QTest.mouseClick(customizer.gui.ui.editDescriptionButton, Qt.LeftButton)
        assert not customizer.gui.ui.editDescriptionButton.isEnabled()
        assert customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert customizer.gui.ui.descriptionTextEdit.isEnabled()

        QTest.mouseClick(customizer.gui.ui.saveDescriptionButton, Qt.LeftButton)
        assert customizer.gui.ui.editDescriptionButton.isEnabled()
        assert not customizer.gui.ui.saveDescriptionButton.isEnabled()
        assert not customizer.gui.ui.descriptionTextEdit.isEnabled()
