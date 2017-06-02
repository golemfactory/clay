from golem.task.taskpreset import (get_task_presets, logger,
                                   delete_task_preset, save_task_preset,
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

        presets = get_task_presets("NewTask")
        assert len(presets) == 1
        assert presets["NewPreset"] == "Data number1"

        data = {"data1": "abc", "data2": 1313}
        save_task_preset("NewPreset2", "NewTask", data)
        presets = get_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number1"
        assert presets["NewPreset2"]["data2"] == 1313

        save_task_preset("NewPreset", "NewTask", "Data number2")
        presets = get_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number2"

        save_task_preset("NewPreset", "NewTask2", "Data number3")
        presets = get_task_presets("NewTask")
        assert len(presets) == 2
        assert presets["NewPreset"] == "Data number2"
        presets = get_task_presets("NewTask2")
        assert len(presets) == 1
        assert presets["NewPreset"] == "Data number3"

        delete_task_preset("NewTask", "NewPreset")
        presets = get_task_presets("NewTask2")
        assert len(presets) == 1
        presets = get_task_presets("NewTask")
        assert len(presets) == 1

    def test_preset_errors(self):
        TaskPreset.drop_table()
        with self.assertLogs(logger, level="WARNING"):
            delete_task_preset("NewTask", "NewPreset")

        with self.assertLogs(logger, level="WARNING"):
            save_task_preset("NewTask", "NewPreset", "data")
