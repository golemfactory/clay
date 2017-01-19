from mock import Mock, patch

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture



from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.startapp import register_task_types
from gui.view.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TestDirFixture, LogTestCase):
    def setUp(self):
        super(TestNewTaskDialogCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gui.app.exit(0)
        self.gui.app.deleteLater()
        super(TestNewTaskDialogCustomizer, self).tearDown()

