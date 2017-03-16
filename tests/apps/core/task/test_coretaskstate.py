from unittest import TestCase

from apps.core.task.coretaskstate import TaskDesc, CoreTaskDefaults, Options

from golem.environments.environment import Environment


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
