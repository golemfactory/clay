import unittest.mock as mock

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture
from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.view.appmainwindow import AppMainWindow


# TODO
class TestDummyTaskCustomizer(TestDirFixture, LogTestCase):
    def setUp(self):
        super(TestDummyTaskCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(mock.Mock(), AppMainWindow)

    def tearDown(self):
        super(TestDummyTaskCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_dummy_customizer(self):
        assert (True)
        pass
