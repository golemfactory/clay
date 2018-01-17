import os
from unittest import TestCase
from unittest.mock import patch

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytask import (
    DummyTaskDefaults,
    DummyTaskBuilder,
    DummyTaskTypeInfo, DummyTask)
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskOptions
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase


class TestDummyTask(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/dummy/task/dummytask.py',
    ]

    def _get_new_dummy(self):
        td = DummyTaskDefinition(DummyTaskDefaults())
        dt = DummyTask(5, "node", td, "root/path", "", "", "")
        return dt, td

    def test_constants(self):
        assert DummyTask.ENVIRONMENT_CLASS == DummyTaskEnvironment
        assert DummyTask.RESULT_EXT == ".result"

    def test_init(self):
        dt, td = self._get_new_dummy()
        assert isinstance(dt, DummyTask)

    def test_new_subtask_id(self):
        dt, td = self._get_new_dummy()
        new_id = dt._DummyTask__get_new_subtask_id()
        assert len(new_id) == 32

    def test_get_result_filename(self):
        dt, td = self._get_new_dummy()
        subtask_id = "aaaaaaa"
        name = dt._DummyTask__get_result_file_name(subtask_id)
        assert name == "{}{}{}".format(td.out_file_basename,
                                       subtask_id[0:6],
                                       dt.RESULT_EXT)

    @patch("random.getrandbits", lambda x: 0)
    def test_query_extra_data_for_test_task(self):
        dt, td = self._get_new_dummy()
        data1 = dt.query_extra_data_for_test_task()
        data2 = dt._extra_data()
        data1['deadline'] = data2['deadline'] = 0
        self.assertEqual(data1['extra_data']["subtask_data"],
                         DummyTask.TESTING_CHAR * td.options.subtask_data_size)
        data1['extra_data']["subtask_data"] = data2['extra_data']["subtask_data"] = ""
        assert data1 == data2

    def test_extra_data(self):
        dt, td = self._get_new_dummy()
        data = dt.query_extra_data(0.0)
        subtask_data_size = td.options.subtask_data_size
        exd = data.ctd['extra_data']
        assert exd["subtask_data_size"] == subtask_data_size
        assert len(exd["subtask_data"]) == subtask_data_size
        assert all(os.path.basename(f) for f in exd["data_files"])
        assert exd["difficulty"] == td.options.difficulty

    def test_accept_results(self):
        dt, td = self._get_new_dummy()
        node_id = "Node"
        data = dt.query_extra_data(0.0, node_id=node_id)

        subtask_id = data.ctd['subtask_id']
        dt.accept_results(subtask_id, [])

        assert dt.num_tasks_received == 1
        assert dt.counting_nodes[node_id]._accepted == 1

        with self.assertRaises(KeyError):
            dt.accept_results("nonexistingsubtask", [])

        with self.assertRaises(Exception):
            dt.accept_results(subtask_id, [])


class TestDummyTaskBuilder(TestCase):

    def test_constants(self):
        assert DummyTaskBuilder.TASK_CLASS == DummyTask

    def test_build_dictionary(self):
        td = DummyTaskDefinition(DummyTaskDefaults())
        dictionary = DummyTaskBuilder.build_dictionary(td)
        opts = dictionary["options"]
        assert opts['subtask_data_size'] == int(td.options.subtask_data_size)
        assert opts['difficulty'] == int(td.options.difficulty)

    def test_build_full_definition(self):
        def get_dict():
            dictionary = {}
            dictionary['resources'] = {"aa"}
            dictionary['subtasks'] = 5
            dictionary['name'] = "name"
            dictionary['bid'] = 5
            dictionary['timeout'] = "5:11:11"
            dictionary['subtask_timeout'] = "5:11:11"
            dictionary['output_path'] = "5:11:11"
            dictionary["options"] = {"output_path": ""}
            return dictionary

        def get_def(difficulty: int, sbs):
            dictionary = get_dict()
            dictionary["options"].update({"subtask_data_size": sbs,
                                          "difficulty": hex(difficulty)})

            return DummyTaskBuilder.build_full_definition(
                DummyTaskTypeInfo(), dictionary)

        difficulty = 15
        sbs = 10
        def_ = get_def(difficulty, sbs)

        assert def_.options.difficulty == difficulty
        assert def_.options.subtask_data_size == sbs

        with self.assertRaises(Exception):
            get_def(-1, 10)
        with self.assertRaises(Exception):
            get_def(10, 0)
        with self.assertRaises(Exception):
            get_def(10, -1)

        # TODO uncomment that when GUI will be fixed
        # with self.assertRaises(TypeError):
        #     get_def("aa", .1)
        # with self.assertRaises(TypeError):
        #     get_def("aa", 10)
        # with self.assertRaises(TypeError):
        #     get_def(.1, -1)
        # with self.assertRaises(TypeError):
        #     get_def(.1, .1)


class TestDummyTaskTypeInfo(TestCase):
    def test_init(self):
        tti = DummyTaskTypeInfo()
        assert tti.name == "Dummy"
        assert tti.options == DummyTaskOptions
        assert isinstance(tti.defaults, DummyTaskDefaults)
        assert tti.task_builder_type == DummyTaskBuilder
        assert tti.definition == DummyTaskDefinition
