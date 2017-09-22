import os
import shutil
from unittest import TestCase
from unittest.mock import patch, MagicMock

import time

from apps.mlpoc.mlpocenvironment import MLPOCTorchEnvironment
from apps.mlpoc.resources.code_pytorch.messages import MLPOCBlackBoxAskMessage, MLPOCBlackBoxAnswerMessage
from apps.mlpoc.task import spearmint_utils
from apps.mlpoc.task.mlpoctask import (
    MLPOCTaskDefaults,
    MLPOCTaskBuilder,
    MLPOCTaskTypeInfo, MLPOCTask)
from apps.mlpoc.task.mlpoctaskstate import MLPOCTaskDefinition, MLPOCTaskOptions
from apps.mlpoc.task.verificator import MLPOCTaskVerificator
from golem.resource.dirmanager import DirManager
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase


class TestMLPOCTask(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/mlpoc/task/mlpoctask.py'
    ]

    def tearDown(self):
        for f in os.listdir(self.tempdir):
            shutil.rmtree(os.path.join(self.tempdir, f), ignore_errors=True)

    @patch("golem.task.localcomputer.LocalComputer", MagicMock)
    def _get_new_mlpoc_no_spearmint(self):
        td = MLPOCTaskDefinition(MLPOCTaskDefaults())
        mlt = MLPOCTask(5, "node", td, self.tempdir, "", "", "")
        return mlt, td

    def _get_new_mlpoc_with_spearmint(self):
        td = MLPOCTaskDefinition(MLPOCTaskDefaults())
        mlt = MLPOCTask(5, "node", td, self.tempdir, "", "", "")
        return mlt, td

    def get_test_mlpoc_task(self):
        defaults = MLPOCTaskDefaults()
        td = MLPOCTaskDefinition(defaults)
        dm = DirManager(self.path)
        db = MLPOCTaskBuilder("MyNodeName", td, self.path, dm)
        return db.build()

    def test_constants(self):
        assert MLPOCTask.VERIFICATOR_CLASS == MLPOCTaskVerificator
        assert MLPOCTask.ENVIRONMENT_CLASS == MLPOCTorchEnvironment
        assert MLPOCTask.RESULT_EXT == ".score"

    def test_init(self):
        mlt, td = self._get_new_mlpoc_with_spearmint()
        self.assertEqual(mlt.spearmint_path, os.path.join(self.tempdir, "tmp"))
        assert isinstance(mlt.verificator, MLPOCTaskVerificator)

    def test_new_subtask_id(self):
        mlt, td = self._get_new_mlpoc_no_spearmint()
        new_id = mlt._MLPOCTask__get_new_subtask_id()
        assert len(new_id) == 32

    def test_get_result_filename(self):
        mlt, td = self._get_new_mlpoc_no_spearmint()
        subtask_id = "aaaaaaa"
        name = mlt._MLPOCTask__get_result_file_name(subtask_id)
        assert name == "{}{}".format(subtask_id[0:6], mlt.RESULT_EXT)

    @patch("golem.docker.job.DockerJob.start", lambda *_:time.sleep(10))
    def test_run_spearmint_in_background(self):
        defaults = MLPOCTaskDefaults()
        td = MLPOCTaskDefinition(defaults)
        dm = DirManager(self.path)
        with patch("golem.resource.dirmanager.DirManager", MagicMock(return_value=dm)):
            spr_dir = os.path.join(self.tempdir, "tmp")
            os.mkdir(spr_dir)

            dm.get_task_temporary_dir = lambda *_, **__: spr_dir
            db = MLPOCTaskBuilder("MyNodeName", td, self.path, dm)
            mlt = db.build() # type: MLPOCTask
        time.sleep(1) # this sleep is needed to properly initialize directories
        assert mlt.spearmint_path == spr_dir
        assert os.path.exists(os.path.join(spr_dir))

        self.assertEqual(mlt.local_spearmint.tmp_dir, spr_dir)

        assert os.path.exists(os.path.join(spr_dir,
                                           "work"))
        assert os.path.exists(os.path.join(spr_dir,
                                           "output"))
        assert os.path.exists(os.path.join(spr_dir,
                                           mlt.SPEARMINT_EXP_DIR))
        assert os.path.exists(os.path.join(spr_dir,
                                           mlt.SPEARMINT_EXP_DIR,
                                           spearmint_utils.CONFIG))
        assert os.path.exists(os.path.join(spr_dir,
                                           mlt.SPEARMINT_EXP_DIR,
                                           spearmint_utils.CONFIG))

    def test_react_to_message(self):
        mlt, td = self._get_new_mlpoc_no_spearmint()
        msg = MLPOCBlackBoxAskMessage.new_message("hash", 15)
        reaction = mlt.react_to_message("subtaskid", {"filename": "out.out",
                                                      "content": msg})
        self.assertIsInstance(reaction, dict)
        self.assertEqual(set(reaction.keys()),
                         set(MLPOCBlackBoxAnswerMessage.new_message(True).keys()))

        # @patch("random.getrandbits", lambda x: 0)
    # def test_query_extra_data_for_test_task(self):
    #     mlt, td = self._get_new_mlpoc()
    #     data1 = mlt.query_extra_data_for_test_task()
    #     data2 = mlt._MLPOCTask__extra_data()
    #     data1.deadline = data2.deadline = 0
    #     self.assertEqual(data1.extra_data["subtask_data"],
    #                      MLPOCTask.TESTING_CHAR * td.options.subtask_data_size)
    #     data1.extra_data["subtask_data"] = data2.extra_data["subtask_data"] = ""
    #     assert data1.__dict__ == data2.__dict__

    # def test_extra_data(self):
    #     mlt, td = self._get_new_mlpoc()
    #     data = mlt.query_extra_data(0.0)
    #     subtask_data_size = td.options.subtask_data_size
    #     exd = data.ctd.extra_data
    #     assert exd["subtask_data_size"] == subtask_data_size
    #     assert len(exd["subtask_data"]) == subtask_data_size
    #     assert all(os.path.basename(f) for f in exd["data_files"])
    #     assert exd["difficulty"] == td.options.difficulty

    # def test_accept_results(self):
    #     mlt, td = self._get_new_mlpoc()
    #     node_id = "Node"
    #     data = mlt.query_extra_data(0.0, node_id=node_id)
    #
    #     subtask_id = data.ctd.subtask_id
    #     mlt.accept_results(subtask_id, [])
    #
    #     assert mlt.num_tasks_received == 1
    #     assert mlt.counting_nodes[node_id]._accepted == 1
    #
    #     with self.assertRaises(KeyError):
    #         mlt.accept_results("nonexistingsubtask", [])
    #
    #     with self.assertRaises(Exception):
    #         mlt.accept_results(subtask_id, [])


# class TestMLPOCTaskBuilder(TestCase):
#     # TODO do the input data validation
#
#     def test_constants(self):
#         assert MLPOCTaskBuilder.TASK_CLASS == MLPOCTask
#
#     def test_build_dictionary(self):
#         td = MLPOCTaskDefinition(MLPOCTaskDefaults())
#         dictionary = MLPOCTaskBuilder.build_dictionary(td)
#         opts = dictionary["options"]
#         assert opts['subtask_data_size'] == int(td.options.subtask_data_size)
#         assert opts['difficulty'] == int(td.options.difficulty)
#
#     def test_build_full_definition(self):
#         td = MLPOCTaskDefinition(MLPOCTaskDefaults())
#
#         def get_dict():
#             dictionary = {}
#             dictionary['resources'] = {"aa"}
#             dictionary['subtasks'] = 5
#             dictionary['name'] = "name"
#             dictionary['bid'] = 5
#             dictionary['timeout'] = "5:11:11"
#             dictionary['subtask_timeout'] = "5:11:11"
#             dictionary['output_path'] = "5:11:11"
#             dictionary["options"] = {"output_path": ""}
#             return dictionary
#
#         def get_def(difficulty, sbs):
#             dictionary = get_dict()
#             dictionary["options"].update({"subtask_data_size": sbs,
#                                           "difficulty": difficulty})
#
#             return MLPOCTaskBuilder.build_full_definition(MLPOCTaskTypeInfo(None, None), dictionary)  # noqa
#
#         difficulty = 20
#         sbs = 10
#         def_ = get_def(difficulty, sbs)
#
#         assert def_.options.difficulty == difficulty
#         assert def_.options.subtask_data_size == sbs
#
#         with self.assertRaises(Exception):
#             get_def(-1, 10)
#         with self.assertRaises(Exception):
#             get_def(10, 0)
#         with self.assertRaises(Exception):
#             get_def(10, -1)
#         with self.assertRaises(Exception):
#             get_def(16 ** 8 + 1, 10)
#         with self.assertRaises(Exception):
#             get_def(16 ** 8, 10)
#
#         pass
#         # TODO uncomment that when GUI will be fixed
#         # with self.assertRaises(TypeError):
#         #     get_def("aa", .1)
#         # with self.assertRaises(TypeError):
#         #     get_def("aa", 10)
#         # with self.assertRaises(TypeError):
#         #     get_def(.1, -1)
#         # with self.assertRaises(TypeError):
#         #     get_def(.1, .1)


class TestMLPOCTaskTypeInfo(TestCase):
    def test_init(self):
        tti = MLPOCTaskTypeInfo(None, None)
        assert tti.name == "MLPOC"
        assert tti.options == MLPOCTaskOptions
        assert isinstance(tti.defaults, MLPOCTaskDefaults)
        assert tti.task_builder_type == MLPOCTaskBuilder
        assert tti.definition == MLPOCTaskDefinition
