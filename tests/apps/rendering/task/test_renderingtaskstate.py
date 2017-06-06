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
        assert defaults.full_task_timeout == 108000

        defaults.resolution = [800, 600]
        assert defaults.subtask_timeout == 1250
        assert defaults.full_task_timeout == 25000


class TestRenderingTaskDefinition(TestCase):

    def test_presets(self):
        tdf = RenderingTaskDefinition()
        tdf.total_subtasks = 12
        tdf.options = "Some option"
        tdf.optimize_total = True
        tdf.verification_options = "Option"
        tdf.resolution = [1111, 2222]
        tdf.output_format = ".exr"

        preset = tdf.make_preset()

        assert len(preset) == 6
        assert preset["total_subtasks"] == 12
        assert preset["options"] == "Some option"
        assert preset["optimize_total"]
        assert preset["verification_options"] == "Option"
        assert preset["output_format"] == ".exr"
        assert preset["resolution"] == [1111, 2222]

        tdf2 = RenderingTaskDefinition()
        assert tdf2.total_subtasks == 0
        assert tdf2.options is None
        assert not tdf2.optimize_total
        assert tdf2.verification_options is None
        assert tdf2.resolution == [0, 0]
        assert tdf2.output_format == ""

        tdf2.load_preset(preset)
        assert tdf2.total_subtasks == 12
        assert tdf2.options == "Some option"
        assert tdf2.optimize_total
        assert tdf2.verification_options == "Option"
        assert tdf2.resolution == [1111, 2222]
        assert tdf2.output_format == ".exr"
