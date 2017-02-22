from unittest import TestCase

from apps.rendering.task.renderingtaskstate import RendererDefaults


class TestRendererDefaults(TestCase):
    def test_timeouts(self):
        defaults = RendererDefaults()
        assert defaults.resolution == [1920, 1080]
        assert defaults.subtask_timeout == 5400
        assert defaults.full_task_timeout == 108000

        defaults.resolution = [800, 600]
        assert defaults.subtask_timeout == 1250
        assert defaults.full_task_timeout == 25000
