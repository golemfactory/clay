import logging

from gui.controller.customizer import Customizer

logger = logging.getLogger("apps.dummy")


class DummyTaskCustomizer(Customizer):
    def get_task_name(self):
        return "DummyTask"
