from unittest import TestCase

from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer
from gnr.gnrstartapp import register_rendering_task_types
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.administrationmainwindow import AdministrationMainWindow
from gnr.ui.dialog import RenderingNewTaskDialog


class TestRenderingNewTaskDialogCustomizer(TestCase):
    def test_customizer(self):
        logic = RenderingApplicationLogic()
        logic.client = Mock()
        register_rendering_task_types(logic)
        gnrgui = GNRGui(Mock(), AdministrationMainWindow)
        customizer = RenderingNewTaskDialogCustomizer(RenderingNewTaskDialog(gnrgui.main_window.window), logic)
        self.assertIsInstance(customizer, RenderingNewTaskDialogCustomizer)
