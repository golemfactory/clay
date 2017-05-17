import os
from pathlib import Path
import pickle
import unittest

from mock import Mock, patch
from PIL import Image

from golem.core.common import is_linux
from golem.resource.dirmanager import DirManager, get_test_task_path
from golem.testutils import PEP8MixIn, TempDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.task.taskbase import ComputeTaskDef

from apps.core.task.coretask import AcceptClientVerdict, TaskTypeInfo
from apps.lux.task.luxrendertask import (logger, LuxRenderDefaults, LuxRenderOptions,
                                         LuxRenderTaskBuilder, LuxRenderTaskTypeInfo)
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition


class TestLuxRenderDefaults(unittest.TestCase):
    def test_init(self):
        ld = LuxRenderDefaults()
        self.assertTrue(os.path.isfile(ld.main_program_file))


class TestLuxRenderTask(TempDirFixture, LogTestCase, PEP8MixIn):
    PEP8_FILES = [
        'apps/lux/task/luxrendertask.py',
    ]

    def get_test_lux_task(self):
        td = RenderingTaskDefinition()
        lro = LuxRenderOptions()
        td.options = lro
        dm = DirManager(self.path)
        lb = LuxRenderTaskBuilder("ABC", td, self.path, dm)
        return lb.build()

    def test_luxtask(self):
        luxtask = self.get_test_lux_task()

        self.__after_test_errors(luxtask)

        self.__queries(luxtask)

    def test_query_extra_data(self):
        luxtask = self.get_test_lux_task()
        luxtask._get_scene_file_rel_path = Mock()
        luxtask._get_scene_file_rel_path.return_value = os.path.join(self.path, 'scene')
        luxtask.main_program_file = os.path.join(self.path, 'program.py')

        luxtask._accept_client = Mock()
        luxtask._accept_client.return_value = AcceptClientVerdict.ACCEPTED

        result = luxtask.query_extra_data(0)
        assert result.ctd is not None
        assert not result.should_wait

        luxtask._accept_client.return_value = AcceptClientVerdict.SHOULD_WAIT

        result = luxtask.query_extra_data(0)
        assert result.ctd is None
        assert result.should_wait

        luxtask._accept_client.return_value = AcceptClientVerdict.REJECTED

        result = luxtask.query_extra_data(0)
        assert result.ctd is None
        assert not result.should_wait

        luxtask._accept_client.return_value = AcceptClientVerdict.ACCEPTED
        result = luxtask.query_extra_data(0)
        assert result.ctd is not None
        assert not result.should_wait

        luxtask.total_tasks = 10
        luxtask.last_task = 10
        result = luxtask.query_extra_data(0)
        assert result.ctd is None
        assert not result.should_wait

    def __after_test_errors(self, luxtask):
        with self.assertLogs(logger, level="WARNING"):
            luxtask.after_test({}, self.path)
        open(os.path.join(self.path, "sth.flm"), 'w').close()
        luxtask.after_test({}, self.path)
        prev_tmp_dir = luxtask.tmp_dir
        luxtask.tmp_dir = "/dev/null/:errors?"
        with self.assertLogs(logger, level="WARNING"):
            luxtask.after_test({}, self.path)
        luxtask.tmp_dir = prev_tmp_dir
        assert os.path.isfile(os.path.join(luxtask.tmp_dir, "test_result.flm"))

    def __queries(self, luxtask):
        luxtask.collected_file_names["xxyyzz"] = "xxyyzzfile"
        luxtask.collected_file_names["abcd"] = "abcdfile"
        ctd = luxtask.query_extra_data_for_final_flm()
        self.assertIsInstance(ctd, ComputeTaskDef)
        assert ctd.src_code is not None
        assert ctd.extra_data['output_flm'] == luxtask.output_file
        assert set(ctd.extra_data['flm_files']) == {"xxyyzzfile", "abcdfile"}

    def test_remove_from_preview(self):
        luxtask = self.get_test_lux_task()
        luxtask.tmp_path = self.path
        luxtask.res_x = 800
        luxtask.res_y = 600
        luxtask.scale_factor = 2
        luxtask._remove_from_preview("UNKNOWN SUBTASK")
        assert os.path.isfile(luxtask.preview_file_path)
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 0, 0)
        image_1 = os.path.join(self.path, "img1.png")
        image_2 = os.path.join(self.path, "img2.png")
        image_3 = os.path.join(self.path, "img3.png")
        img = Image.new("RGB", (luxtask.res_x, luxtask.res_y), color="#ff0000")
        img.save(image_1)
        img2 = Image.new("RGB", (luxtask.res_x, luxtask.res_y), color="#00ff00")
        img2.save(image_2)
        img3 = Image.new("RGB", (luxtask.res_x, luxtask.res_y), color="#0000ff")
        img3.save(image_3)
        luxtask.subtasks_given["SUBTASK1"] = {"status": 'Finished', 'preview_file': image_1}
        luxtask.subtasks_given["SUBTASK2"] = {"status": 'Finished', 'preview_file': image_2}
        luxtask._remove_from_preview("SUBTASK1")
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 255, 0)
        luxtask.subtasks_given["SUBTASK3"] = {"status": 'Finished', 'preview_file': image_3}
        luxtask._remove_from_preview("SUBTASK1")
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 127, 127)
        luxtask.subtasks_given["SUBTASK4"] = {"status": 'Not inished',
                                              'preview_file': "not a file"}
        luxtask._remove_from_preview("SUBTASK1")
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 127, 127)

    def test_accept_results(self):
        luxtask = self.get_test_lux_task()
        luxtask.total_tasks = 20
        luxtask.res_x = 800
        luxtask.res_y = 600
        img_file = os.path.join(self.path, "image1.png")
        img = Image.new("RGB", (800, 600), "#00ff00")
        img.save(img_file)
        img.close()
        flm_file = os.path.join(self.path, "result.flm")
        open(flm_file, 'w').close()
        luxtask.subtasks_given["SUBTASK1"] = {"start_task": 1, "node_id": "NODE_1"}
        log_file = self.temp_file_name("stdout.log")

        luxtask._accept_client("NODE_1")
        luxtask.accept_results("SUBTASK1", [img_file, flm_file, log_file])

        assert luxtask.subtasks_given["SUBTASK1"]['preview_file'] == img_file
        assert os.path.isfile(luxtask.preview_file_path)
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 255, 0)
        preview_img.close()
        assert luxtask.num_tasks_received == 1
        assert luxtask.collected_file_names[1] == flm_file

    def test_pickling(self):
        """Test for issue #873

        https://github.com/golemfactory/golem/issues/873
        """
        p = Path(__file__).parent / "samples" / "GoldenGate.exr"
        luxtask = self.get_test_lux_task()
        luxtask.res_x, luxtask.res_y = 1262, 860
        luxtask._update_preview_from_exr(str(p))
        pickled = pickle.dumps(luxtask)

    def test_query_extra_data_for_test_task(self):
        # make sure that test task path is creatd
        luxtask = self.get_test_lux_task()
        luxtask._get_scene_file_rel_path = Mock()
        luxtask._get_scene_file_rel_path.return_value = os.path.join(self.path, 'scene')
        assert not os.path.exists(get_test_task_path(luxtask.root_path))
        luxtask.query_extra_data_for_test_task()
        assert os.path.exists(get_test_task_path(luxtask.root_path))

    def test_update_task_preview(self):
        luxtask = self.get_test_lux_task()
        luxtask._update_task_preview()

    @patch("apps.lux.task.luxrendertask.find_task_script")
    def test_get_merge_ctd_error(self, find_task_script_mock):
        # If Lux cannot find merge script, an error log should be returned
        find_task_script_mock.return_value = None

        with self.assertLogs(logger, level="ERROR") as l:
            assert self.get_test_lux_task()

        assert any("Cannot find merger script" in log for log in l.output)

    def test_update_preview_with_exr(self):
        p = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile.EXR"
        luxtask = self.get_test_lux_task()
        luxtask.res_x, luxtask.res_y = 10, 10
        luxtask._update_preview(str(p), 1)
        # Run update again (should blend)
        luxtask._update_preview(str(p), 2)

    def test_errors(self):
        luxtask = self.get_test_lux_task()
        luxtask.output_format = "png"
        luxtask.output_file = os.path.join(self.path, "inside", "outputfile")
        os.makedirs(os.path.join(self.path, "inside"))
        with self.assertLogs(logger, level="ERROR") as l:
            luxtask._LuxTask__final_flm_failure("some error")
        assert any("some error" in log for log in l.output)

        with self.assertLogs(logger, level="ERROR") as l:
            luxtask._LuxTask__final_img_error("different error")
        assert any("different error" in log for log in l.output)

        with self.assertLogs(logger, level="ERROR") as l:
            luxtask._LuxTask__final_img_ready({"data": self.additional_dir_content([1, [2]])}, 10)
        assert any("No final file generated" in log for log in l.output)

        with self.assertLogs(logger, level="ERROR") as l:
            luxtask._LuxTask__final_flm_ready({"data": self.additional_dir_content([1, [2]])}, 10)
        assert any("No flm file created" in log for log in l.output)

        if not is_linux():
            return

        output_file = os.path.join(self.path, "inside", "outputfile.png")
        with open(output_file, 'w') as f:
            f.write("not empty")

        os.chmod(output_file, 0o400)

        assert os.path.isfile(os.path.join(self.path, "inside", "outputfile.png"))
        diff_output = self.temp_file_name("diff_output.png")

        with open(self.temp_file_name("diff_output.png"), 'w') as f:
            f.write("not_empty")
        with self.assertLogs(logger, level="WARNING") as l:
            luxtask._LuxTask__final_img_ready({"data": self.additional_dir_content([1, [2]]) +
                                                       [diff_output]}, 10)
        assert any("Couldn't rename" in log for log in l.output)

        os.chmod(output_file, 0o700)


class TestLuxRenderTaskTypeInfo(TempDirFixture):
    def test_init(self):
        typeinfo = LuxRenderTaskTypeInfo("dialog", "controller")
        assert isinstance(typeinfo, TaskTypeInfo)
        assert typeinfo.output_formats == ["exr", "png", "tga"]
        assert typeinfo.output_file_ext == ["lxs"]
        assert typeinfo.name == "LuxRender"
        assert isinstance(typeinfo.defaults, LuxRenderDefaults)
        assert typeinfo.options == LuxRenderOptions
        assert typeinfo.definition == RenderingTaskDefinition
        assert typeinfo.task_builder_type == LuxRenderTaskBuilder
        assert typeinfo.dialog == "dialog"
        assert typeinfo.dialog_controller == "controller"

    def test_get_task_border(self):
        typeinfo = LuxRenderTaskTypeInfo(None, None)
        definition = RenderingTaskDefinition()
        definition.resolution = (4, 4)
        border = typeinfo.get_task_border("subtask1", definition, 10)
        for i in range(4):
            assert (i, 0) in border
            assert (i, 3) in border
        for j in range(4):
            assert (0, j) in border
            assert (3, j) in border

        definition.resolution = (300, 200)
        border = typeinfo.get_task_border("subtask1", definition, 10)
        for i in range(300):
            assert (i, 0) in border
            assert (i, 199) in border
        for j in range(200):
            assert (0, j) in border
            assert (299, j) in border
        assert (300, 199) not in border
        assert (299, 201) not in border
        assert (0, 200) not in border
        assert (300, 0) not in border

        definition.resolution = (300, 300)
        border = typeinfo.get_task_border("subtask1", definition, 10)
        for i in range(200):
            assert (i, 0) in border
            assert (i, 199) in border
        for j in range(200):
            assert (0, j) in border
            assert (199, j) in border
        assert (200, 199) not in border
        assert (199, 200) not in border
        assert (0, 200) not in border
        assert (200, 0) not in border

        definition.resolution = (1000, 100)
        border = typeinfo.get_task_border("subtask1", definition, 10)
        for i in range(300):
            assert (i, 0) in border
            assert (i, 29) in border
        for j in range(30):
            assert (0, j) in border
            assert (299, j) in border
        assert (30, 299) not in border
        assert (29, 200) not in border
        assert (0, 30) not in border
        assert (300, 0) not in border

        definition.resolution = (100, 1000)
        border = typeinfo.get_task_border("subtask1", definition, 10)
        for i in range(20):
            assert (i, 0) in border
            assert (i, 199) in border
        for j in range(200):
            assert (0, j) in border
            assert (19, j) in border
        assert (20, 199) not in border
        assert (19, 200) not in border
        assert (20, 0) not in border
        assert (0, 200) not in border

        definition.resolution = (0, 4)
        assert typeinfo.get_task_border("subtask1", definition, 10) == []
        definition.resolution = (4, 0)
        assert typeinfo.get_task_border("subtask1", definition, 10) == []
        definition.resolution = (0, 0)
        assert typeinfo.get_task_border("subtask1", definition, 10) == []

    def test_get_task_num_from_pixels(self):
        typeinfo = LuxRenderTaskTypeInfo(None, None)
        definition = RenderingTaskDefinition()
        definition.resolution = (0, 0)
        assert typeinfo.get_task_num_from_pixels(10, 10, definition, 10) == 1
