import jsonpickle

from golem.task.taskpreset import (load_task_presets, logger,
                                   remove_task_preset, save_task_preset,
                                   TaskPreset)
from golem.testutils import PEP8MixIn
from golem.tools.assertlogs import LogTestCase
from golem.tools.testwithdatabase import TestWithDatabase


class TestTaskPresets(TestWithDatabase, PEP8MixIn, LogTestCase):
    PEP8_FILES = [
        "golem/task/taskpreset.py"
    ]

    def test_task_preset(self):
        save_task_preset("NewPreset", "NewTask", "Data number1")

        presets = load_task_presets("NewTask")
        assert len(presets) == 1
        assert presets["NewPreset"] == "Data number1"

        data = jsonpickle.dumps({"data1": "abc", "data2": 1313})
        save_task_preset("NewPreset2", "NewTask", data)
        presets = load_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number1"
        assert jsonpickle.loads(presets["NewPreset2"])["data2"] == 1313

        save_task_preset("NewPreset", "NewTask", "Data number2")
        presets = load_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number2"

        save_task_preset("NewPreset", "NewTask2", "Data number3")
        presets = load_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number2"
        presets = load_task_presets("NewTask2")
        assert len(presets) == 1
        assert presets["NewPreset"] == "Data number3"

        remove_task_preset("NewTask", "NewPreset")
        presets = load_task_presets("NewTask2")
        assert len(presets) == 1
        presets = load_task_presets("NewTask")
        assert len(presets) == 1

    def test_preset_errors(self):
        TaskPreset.drop_table()
        with self.assertLogs(logger, level="WARNING"):
            remove_task_preset("NewTask", "NewPreset")

        with self.assertLogs(logger, level="WARNING"):
            save_task_preset("NewTask", "NewPreset", "data")
