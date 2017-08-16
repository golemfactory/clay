import os

from apps.dummy.task.dummytask import DummyTask
from apps.dummy.task.dummytaskstate import DummyTaskDefaults, DummyTaskDefinition
from apps.dummy.task.verificator import DummyTaskVerificator
from golem.testutils import TempDirFixture


class TestDummyTaskVerificator(TempDirFixture):
    def test_init(self):
        dv = DummyTaskVerificator()
        assert isinstance(dv.verification_options, dict)

    def test_verify_result(self):
        correct_solution = 0x8e3b3
        temporary = 0
        shared_file = os.path.join(self.tempdir, "input_file.txt")
        with open(shared_file, "w") as f:
            f.write("AAAA")

        good_result_file = os.path.join(self.tempdir, "good_result_file.txt")
        with open(good_result_file, "w") as f:
            f.write("%x" % correct_solution)

        bad_length_result_file = os.path.join(self.tempdir, "bad_length_result_file.txt")
        with open(bad_length_result_file, "w") as f:
            f.write("0xccb330")

        bad_num_result_file = os.path.join(self.tempdir, "bad_num_result_file.txt")
        with open(bad_num_result_file, "w") as f:
            f.write("%x" % (correct_solution + 1))

        dd = DummyTaskDefaults()
        dd.result_size = 5
        dd.shared_data_files = [shared_file]

        td = DummyTaskDefinition(dd)
        dt = DummyTask(3, "a", td, self.tempdir)
        ver = dt.verificator
        ver_opts = ver.verification_options

        assert isinstance(dt.verificator, DummyTaskVerificator)
        assert isinstance(ver_opts, dict)
        assert set(ver_opts.keys()) == {"difficulty", "shared_data_files", "result_size"}
        assert ver_opts["difficulty"] == td.options.difficulty
        assert ver_opts["shared_data_files"] == td.shared_data_files
        assert ver_opts["result_size"] == td.result_size

        subtask_data = {"subtask_data": "0" * 128}

        # zero difficulty condition
        ver.verification_options["difficulty"], temporary = temporary, ver.verification_options["difficulty"]
        self.assertFalse(ver._verify_result(0, subtask_data, bad_length_result_file, None))
        self.assertTrue(ver._verify_result(0, subtask_data, good_result_file, None))
        self.assertTrue(ver._verify_result(0, subtask_data, bad_num_result_file, None))
        ver.verification_options["difficulty"], temporary = temporary, ver.verification_options["difficulty"]

        # result size length condition
        self.assertFalse(ver._verify_result(0, subtask_data, bad_length_result_file, None))

        # non-existing file
        with self.assertRaises(IOError):
            ver._verify_result(0, subtask_data, "non/non/nonfile", None)

        # good result
        assert ver._verify_result(0, subtask_data, good_result_file, None)

        # changing subtask data
        changed_subtask_data = {"subtask_data": "1" * 128}
        self.assertFalse(ver._verify_result(0, changed_subtask_data, good_result_file, None))
