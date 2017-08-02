from PyQt5.QtCore import Qt, QSettings
from PyQt5.QtTest import QTest
from mock import Mock, patch
import os

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture

from apps.lux.gui.controller.luxrenderdialogcustomizer import LuxRenderDialogCustomizer, logger
from apps.lux.gui.view.gen.ui_LuxWidget import Ui_LuxWidget
from apps.lux.task.luxrendertask import LuxRenderTaskTypeInfo
from gui.controller.mainwindowcustomizer import MainWindowCustomizer
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition

from gui.application import Gui
from gui.applicationlogic import GuiApplicationLogic
from gui.view.appmainwindow import AppMainWindow
from gui.view.widget import TaskWidget

#DOIT
class TestDummyTaskCustomizer(TestDirFixture, LogTestCase):

    def setUp(self):
        super(TestDummyTaskCustomizer, self).setUp()
        self.logic = GuiApplicationLogic()
        self.gui = Gui(Mock(), AppMainWindow)

    def tearDown(self):
        super(TestDummyTaskCustomizer, self).tearDown()
        self.gui.app.exit(0)
        self.gui.app.deleteLater()

    def test_dummy_customizer(self):
        assert(True)
        pass