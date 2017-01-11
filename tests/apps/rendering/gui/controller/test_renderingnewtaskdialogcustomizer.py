from mock import Mock, patch

from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture



from gui.application import GNRGui
from gui.applicationlogic import GNRApplicationLogic
from gui.startapp import register_task_types
from gui.view.appmainwindow import AppMainWindow


class TestNewTaskDialogCustomizer(TestDirFixture, LogTestCase):
    def setUp(self):
        super(TestNewTaskDialogCustomizer, self).setUp()
        self.logic = GNRApplicationLogic()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()
        super(TestNewTaskDialogCustomizer, self).tearDown()

