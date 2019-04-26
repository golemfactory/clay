from unittest import TestCase

from apps.rendering.task.renderingtaskstate import (RendererDefaults,
                                                    RenderingTaskDefinition)

from golem.testutils import PEP8MixIn


class TestRenderingTaskStateStyle(TestCase, PEP8MixIn):

    PEP8_FILES = [
        "apps/rendering/task/renderingtaskstate.py"
    ]


class TestRendererDefaults(TestCase):

    def test_timeouts(self):
        defaults = RendererDefaults()
        assert defaults.resolution == [1920, 1080]
        assert defaults.subtask_timeout == 5400
        assert defaults.timeout == 108000

        defaults.resolution = [800, 600]
        assert defaults.subtask_timeout == 1250
        assert defaults.timeout == 25000
