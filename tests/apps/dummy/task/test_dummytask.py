from unittest import TestCase

import os
from unittest.mock import patch

from apps.dummy.dummyenvironment import DummyTaskEnvironment
from apps.dummy.task.dummytask import (
    DummyTaskDefaults,
    DummyTaskBuilder,
    DummyTaskTypeInfo, DummyTask)
from apps.dummy.task.dummytaskstate import DummyTaskDefinition, DummyTaskOptions
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.resource.dirmanager import DirManager
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

    def get_test_dummy_task(self):
        defaults = DummyTaskDefaults()
        td = DummyTaskDefinition(defaults)
        dm = DirManager(self.path)
        db = DummyTaskBuilder("MyNodeName", td, self.path, dm)
        return db.build()

    def test_constants(self):
        assert DummyTask.VERIFICATOR_CLASS == DummyTaskVerificator
        assert DummyTask.ENVIRONMENT_CLASS == DummyTaskEnvironment
        assert DummyTask.RESULT_EXTENSION == ".result"

    def test_init(self):
        dt, td = self._get_new_dummy()
        assert isinstance(dt.verificator, DummyTaskVerificator)

        ver_opts = dt.verificator.verification_options
        assert ver_opts["difficulty"] == td.options.difficulty
        assert ver_opts["shared_data_files"] == td.shared_data_files
        assert ver_opts["result_size"] == td.result_size

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
                                       dt.RESULT_EXTENSION)

    @patch("random.getrandbits", lambda x: 0)
    def test_query_extra_data_for_test_task(self):
        dt, _ = self._get_new_dummy()
        data1 = dt.query_extra_data_for_test_task()
        data2 = dt._extra_data()
        data1.deadline = data2.deadline = 0
        assert data1.__dict__ == data2.__dict__

    def test_extra_data(self):
        dt, td = self._get_new_dummy()
        data = dt.query_extra_data(0.0)
        subtask_data_size = td.options.subtask_data_size
        exd = data.ctd.extra_data
        assert exd["subtask_data_size"] == subtask_data_size
        assert len(exd["subtask_data"]) == subtask_data_size
        assert all(os.path.basename(f) for f in exd["data_files"])
        assert exd["difficulty"] == td.options.difficulty

    def test_accept_results(self):
        dt, td = self._get_new_dummy()
        node_id = "Node"
        data = dt.query_extra_data(0.0, node_id=node_id)

        subtask_id = data.ctd.subtask_id
        dt.accept_results(subtask_id, [])

        assert dt.num_tasks_received == 1
        assert dt.counting_nodes[node_id]._accepted == 1

        with self.assertRaises(KeyError):
            dt.accept_results("nonexistingsubtask", [])

        with self.assertRaises(Exception):
            dt.accept_results(subtask_id, [])


class TestDummyTaskBuilder(TestCase):
    # TODO do the input data validation

    def test_constants(self):
        assert DummyTaskBuilder.TASK_CLASS == DummyTask

    def test_build_dictionary(self):



class TestDummyTaskTypeInfo(TestCase):
    def test_init(self):
        tti = DummyTaskTypeInfo(None, None)
        assert tti.name == "Dummy"
        assert tti.options == DummyTaskOptions
        assert isinstance(tti.defaults, DummyTaskDefaults)
        assert tti.task_builder_type == DummyTaskBuilder
        assert tti.definition == DummyTaskDefinition

