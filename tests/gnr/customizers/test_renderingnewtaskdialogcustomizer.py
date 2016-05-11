from unittest import TestCase

from mock import Mock

from gnr.application import GNRGui
from gnr.customizers.renderingnewtaskdialogcustomizer import RenderingNewTaskDialogCustomizer
from gnr.gnrstartapp import register_rendering_task_types
from gnr.renderingapplicationlogic import RenderingApplicationLogic
from gnr.ui.appmainwindow import AppMainWindow


class TestRenderingNewTaskDialogCustomizer(TestCase):
    def test_customizer(self):
        gnrgui = GNRGui(Mock(), AppMainWindow)
        logic = RenderingApplicationLogic()
        logic.client = Mock()
        register_rendering_task_types(logic)
        customizer = RenderingNewTaskDialogCustomizer(gnrgui.main_window, logic)
        self.assertIsInstance(customizer, RenderingNewTaskDialogCustomizer)
        gnrgui.app.exit(0)
        gnrgui.app.deleteLater()

