import os
import uuid

from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, \
    DummyTaskDefinition
from apps.dummy.task.verifier import DummyTaskVerifier
from golem.testutils import TempDirFixture


class TestDummyTaskVerifier(TempDirFixture):
    def test_init(self):
        def callback():
            pass
        dv = DummyTaskVerifier(callback)
        assert isinstance(dv, DummyTaskVerifier)

    def test_verify_result(self):
        correct_solution = 0x8e3b3
        tmp = 0
        shared_file = os.path.join(self.tempdir, "input_file.result")
        with open(shared_file, "w") as f:
            f.write("AAAA")

        good_result_file = os.path.join(self.tempdir, "good_result_file.result")
        with open(good_result_file, "w") as f:
            f.write("%x" % correct_solution)

        bad_length_result_file = os.path.join(self.tempdir,
                                              "bad_length_result_file.result")
        with open(bad_length_result_file, "w") as f:
            f.write("0xccb330")

        bad_num_result_file = os.path.join(self.tempdir,
                                           "bad_num_result_file.result")
        with open(bad_num_result_file, "w") as f:
            f.write("%x" % (correct_solution + 1))

        bad_ext_result_file = os.path.join(self.tempdir,
                                           "bad_ext_result_file.txt")
        with open(bad_ext_result_file, "w") as f:
            f.write("%x" % (correct_solution))

        dd = DummyTaskDefaults()
        dd.result_size = 5
        dd.shared_data_files = [shared_file]

        td = DummyTaskDefinition(dd)
        td.task_id = str(uuid.uuid4())
        dt = DummyTask(3, "a", td, self.tempdir)
        ver = DummyTaskVerifier(lambda: None)
        ed = dt.query_extra_data(perf_index=1.0)
        ver_opts = dt.subtasks_given[ed.ctd['subtask_id']]

        assert isinstance(ver_opts, dict)
        assert all(key in ver_opts.keys() for key in ["difficulty",
                                                      "shared_data_files",
                                                      "result_size",
                                                      "result_extension"])
        assert ver_opts["difficulty"] == td.options.difficulty
        assert ver_opts["shared_data_files"] == td.shared_data_files
        assert ver_opts["result_size"] == td.result_size
        assert ver_opts["result_extension"] == DummyTask.RESULT_EXT

        ver_opts["subtask_data"] = "0" * 128
        subtask_data = ver_opts

        # zero difficulty condition
        ver_opts["difficulty"], tmp = tmp, ver_opts["difficulty"]  # noqa
        self.assertFalse(ver._verify_result(subtask_data,
                                            result=bad_length_result_file,
                                            reference_data=[],
                                            resources=[]))  # noqa
        self.assertTrue(ver._verify_result(subtask_data,
                                           result=good_result_file,
                                           reference_data=[],
                                           resources=[]))  # noqa
        self.assertFalse(ver._verify_result(subtask_data,
                                            result=bad_ext_result_file,
                                            reference_data=[],
                                            resources=[]))  # noqa
        self.assertTrue(ver._verify_result(subtask_data,
                                           result=bad_num_result_file,
                                           reference_data=[],
                                           resources=[]))  # noqa
        ver_opts["difficulty"], tmp = tmp, ver_opts["difficulty"]  # noqa

        # result size length condition
        self.assertFalse(ver._verify_result(subtask_data,
                                            bad_length_result_file,
                                            [], []))  # noqa

        # non-existing file
        with self.assertRaises(IOError):
            ver._verify_result(subtask_data, "non/non/nonfile.result", [], [])

        # good result
        assert ver._verify_result(subtask_data, good_result_file, [], [])

        # changing subtask data
        ver_opts["subtask_data"] = "1" * 128
        changed_subtask_data = ver_opts
        self.assertFalse(ver._verify_result(changed_subtask_data,
                                            good_result_file, [], []))  # noqa
