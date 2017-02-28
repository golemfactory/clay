import unittest
import os

from mock import Mock
from PIL import Image

from golem.resource.dirmanager import DirManager
from golem.tools.testdirfixture import TestDirFixture
from golem.tools.assertlogs import LogTestCase
from golem.task.taskbase import ComputeTaskDef

from apps.lux.task.luxrendertask import LuxRenderDefaults, LuxRenderTaskBuilder, LuxRenderOptions, logger
from apps.rendering.task.renderingtask import AcceptClientVerdict

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition


class TestLuxRenderDefaults(unittest.TestCase):
    def test_init(self):
        ld = LuxRenderDefaults()
        self.assertTrue(os.path.isfile(ld.main_program_file))


class TestLuxRenderTaskBuilder(TestDirFixture, LogTestCase):

    def __get_test_lux_task(self):
        td = RenderingTaskDefinition()
        lro = LuxRenderOptions()
        td.options = lro
        dm = DirManager(self.path)
        lb = LuxRenderTaskBuilder("ABC", td, self.path, dm)
        return  lb.build()


    def test_luxtask(self):
        luxtask = self.__get_test_lux_task()

        self.__after_test_errors(luxtask)

        self.__queries(luxtask)

    def test_query_extra_data(self):
        luxtask = self.__get_test_lux_task()
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
        luxtask = self.__get_test_lux_task()
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
        luxtask = self.__get_test_lux_task()
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

        luxtask._accept_client("NODE_1")
        luxtask.accept_results("SUBTASK1", [img_file, flm_file])

        assert luxtask.subtasks_given["SUBTASK1"]['preview_file'] == img_file
        assert os.path.isfile(luxtask.preview_file_path)
        preview_img = Image.open(luxtask.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 255, 0)
        preview_img.close()
        assert luxtask.num_tasks_received == 1
        assert luxtask.collected_file_names[1] == flm_file



