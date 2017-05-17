from unittest import TestCase

from apps.core.task.coretaskstate import (CoreTaskDefaults, Options,
                                          TaskDefinition, TaskDesc)

from golem.environments.environment import Environment
from golem.testutils import PEP8MixIn


class TestTaskDesc(TestCase):
    def test_init(self):
        td = TaskDesc()
        self.assertIsInstance(td, TaskDesc)


class TestCoreTaskDefautls(TestCase):
    def test_init(self):
        defaults = CoreTaskDefaults()
        assert defaults.output_format == ""
        assert defaults.main_program_file == ""
        assert defaults.full_task_timeout == 4 * 3600
        assert defaults.subtask_timeout == 20 * 60
        assert defaults.min_subtasks == 1
        assert defaults.max_subtasks == 50
        assert defaults.default_subtasks == 20
        assert defaults.task_name == ""


class TestOptions(TestCase):
    def test_option(self):
        opt = Options()
        assert isinstance(opt.environment, Environment)
        assert opt.name == ""
        opt.add_to_resources([])
        opt.remove_from_resources([])


class TestCoreTaskStateStyle(TestCase, PEP8MixIn):
    PEP8_FILES = [
        "apps/core/task/coretaskstate.py"
    ]


class TestTaskDefinition(TestCase):

    def test_preset(self):
        tdf = TaskDefinition()
        tdf.total_subtasks = 12
        tdf.options.name = "OptionsName"
        tdf.optimize_total = True
        tdf.verification_options = "Option"
        preset = tdf.make_preset()
        assert len(preset) == 4
        assert preset["options"].name == "OptionsName"
        assert preset["verification_options"] == "Option"
        assert preset["total_subtasks"] == 12
        assert preset["optimize_total"]

        tdf2 = TaskDefinition()
        assert tdf2.options.name == ""
        assert tdf2.verification_options is None
        assert tdf2.total_subtasks == 0
        assert not tdf2.optimize_total

        tdf2.load_preset(preset)
        assert tdf2.options.name == "OptionsName"
        assert tdf2.verification_options == "Option"
        assert tdf2.total_subtasks == 12
        assert tdf2.optimize_total
