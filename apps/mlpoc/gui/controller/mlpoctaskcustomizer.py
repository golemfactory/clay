import logging

from gui.controller.customizer import Customizer

logger = logging.getLogger("apps.mlpoc")


class MLPOCTaskCustomizer(Customizer):
    def get_task_name(self):
        return "MLPOC"
