import pickle
from unittest import mock
from unittest import TestCase

from apps.core.task.coretaskstate import (
    Options,
    TaskDefaults,
    TaskDefinition,
    TaskDesc,
)

from golem.environments.environment import Environment
from golem.testutils import PEP8MixIn


class TestTaskDesc(TestCase):
    def test_init(self):
        td = TaskDesc()
        self.assertIsInstance(td, TaskDesc)


class TestCoreTaskDefautls(TestCase):
    def test_init(self):
        defaults = TaskDefaults()
        assert defaults.output_format == ""
        assert defaults.main_program_file == ""
        assert defaults.timeout == 4 * 3600
        assert defaults.subtask_timeout == 20 * 60
        assert defaults.min_subtasks == 1
        assert defaults.max_subtasks == 50
        assert defaults.default_subtasks == 20
        assert defaults.name == ""


class TestOptions(TestCase):
    def test_option(self):
        opt = Options()
        assert isinstance(opt.environment, Environment)
        assert opt.name == ""


class TestCoreTaskStateStyle(TestCase, PEP8MixIn):
    PEP8_FILES = [
        "apps/core/task/coretaskstate.py"
    ]


class TestTaskDefinition(TestCase):

    def test_preset(self):
        tdf = TaskDefinition()
        tdf.subtasks_count = 12
        tdf.options.name = "OptionsName"
        tdf.optimize_total = True
        tdf.verification_options = "Option"
        preset = tdf.make_preset()
        assert len(preset) == 4
        assert preset["options"].name == "OptionsName"
        assert preset["verification_options"] == "Option"
        assert preset["subtasks_count"] == 12
        assert preset["optimize_total"]

        tdf2 = TaskDefinition()
        assert tdf2.options.name == ""
        assert tdf2.verification_options is None
        assert tdf2.subtasks_count == 0
        assert not tdf2.optimize_total

        tdf2.load_preset(preset)
        assert tdf2.options.name == "OptionsName"
        assert tdf2.verification_options == "Option"
        assert tdf2.subtasks_count == 12
        assert tdf2.optimize_total


class TestPicklesFrom_0_17_1(TestCase):
    def setUp(self):
        self.task_definition = TaskDefinition()
        self.assertTrue(hasattr(self.task_definition, 'compute_on'))
        self.assertTrue(hasattr(self.task_definition, 'concent_enabled'))
        super().setUp()

    def ser_deser(self):
        pickled = pickle.dumps(self.task_definition)
        self.task_definition = pickle.loads(pickled)

    def test_missing_compute_on(self, *_):
        del self.task_definition.compute_on
        with mock.patch(
            'apps.core.task.coretaskstate.TaskDefinition.__getstate__',
            side_effect=lambda: self.task_definition.__dict__,
        ):
            self.ser_deser()
        self.assertEqual(self.task_definition.compute_on, 'cpu')

    def test_missing_concent_enabled(self, *_):
        del self.task_definition.concent_enabled
        with mock.patch(
            'apps.core.task.coretaskstate.TaskDefinition.__getstate__',
            side_effect=lambda: self.task_definition.__dict__,
        ):
            self.ser_deser()
        self.assertEqual(self.task_definition.concent_enabled, False)


class TestPicklesFrom_0_18_0(TestCase):
    def setUp(self):
        self.task_definition = TaskDefinition()
        self.assertTrue(hasattr(self.task_definition, 'name'))
        self.assertTrue(hasattr(self.task_definition, 'timeout'))
        self.assertTrue(hasattr(self.task_definition, 'subtasks_count'))
        super().setUp()

    def ser_deser(self):
        pickled = pickle.dumps(self.task_definition)
        self.task_definition = pickle.loads(pickled)

    def test_old_attributes_version_0(self, *_):
        del self.task_definition.name
        del self.task_definition.timeout
        del self.task_definition.subtasks_count
        self.task_definition.task_name = 'some_name'
        self.task_definition.full_task_timeout = '00:01:00'
        self.task_definition.total_subtasks = 1
        with mock.patch(
            'apps.core.task.coretaskstate.TaskDefinition.__getstate__',
            side_effect=lambda: self.task_definition.__dict__,
        ):
            self.ser_deser()
        self.assertEqual(self.task_definition.name, 'some_name')
        self.assertEqual(self.task_definition.timeout, '00:01:00')
        self.assertEqual(self.task_definition.subtasks_count, 1)

    def test_old_attributes_version_1(self, *_):
        del self.task_definition.name
        del self.task_definition.timeout
        del self.task_definition.subtasks_count
        self.task_definition.task_name = 'some_name'
        self.task_definition.full_task_timeout = '00:01:00'
        self.task_definition.total_subtasks = 1
        with mock.patch(
            'apps.core.task.coretaskstate.TaskDefinition.__getstate__',
            side_effect=lambda: ("0.18.0", self.task_definition.__dict__),
        ):
            self.ser_deser()
        self.assertEqual(self.task_definition.name, 'some_name')
        self.assertEqual(self.task_definition.timeout, '00:01:00')
        self.assertEqual(self.task_definition.subtasks_count, 1)
