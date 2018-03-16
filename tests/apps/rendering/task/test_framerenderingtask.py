import os
import unittest
import uuid
from pathlib import Path

from PIL import Image

from apps.rendering.resources.imgrepr import load_img, EXRImgRepr
from apps.rendering.task.framerenderingtask import (get_frame_name, FrameRenderingTask,
                                                    FrameRenderingTaskBuilder,
                                                    FrameRendererOptions, logger)
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class FrameRenderingTaskMock(FrameRenderingTask):
    class ENVIRONMENT_CLASS(object):
        main_program_file = None
        docker_images = []

        def get_id(self):
            return "TEST"

    def __init__(self, main_program_file, *args, **kwargs):
        self.ENVIRONMENT_CLASS.main_program_file = main_program_file
        super(FrameRenderingTaskMock, self).__init__(*args, **kwargs)

    def query_extra_data(*args, **kwargs):
        pass

    def query_extra_data_for_test_task(self):
        pass


class TestFrameRenderingTask(TestDirFixture, LogTestCase):
    def _get_frame_task(self, use_frames=True):
        files_ = self.additional_dir_content([3])
        rt = RenderingTaskDefinition()
        rt.options = FrameRendererOptions()
        rt.options.use_frames = use_frames
        rt.options.frames = list(range(6))
        rt.main_scene_file = files_[1]
        rt.output_format = "PNG"
        rt.output_file = files_[2]
        rt.resources = []
        rt.resolution = [800, 600]
        rt.full_task_timeout = 3600
        rt.subtask_timeout = 600
        rt.estimated_memory = 1000
        rt.max_price = 15
        task = FrameRenderingTaskMock(files_[0],
                                      node_name="ABC",
                                      task_definition=rt,
                                      total_tasks=3,
                                      root_path=self.path
                                      )
        dm = DirManager(self.path)
        task.initialize(dm)
        return task

    def test_get_frame_name(self):
        assert get_frame_name("ABC", "png", 124) == "ABC0124.png"
        assert get_frame_name("QWERT_", "EXR", 13) == "QWERT_0013.EXR"
        assert get_frame_name("IMAGE_###", "jpg", 4) == "IMAGE_004.jpg"
        assert get_frame_name("IMAGE_###_VER_131", "JPG", 23) == "IMAGE_023_VER_131.JPG"
        assert get_frame_name("IMAGE_###_ABC", "exr", 1023) == "IMAGE_1023_ABC.exr"
        assert get_frame_name("##_#####", "png", 3) == "##_00003.png"
        assert get_frame_name("#####_###", "PNG", 27) == "#####_027.PNG"

    def test_accept_results(self):
        task = self._get_frame_task(use_frames=False)
        task._accept_client("NODE 1")
        task.tmp_dir = self.path
        task.subtasks_given["SUBTASK1"] = {"start_task": 3, "node_id": "NODE 1", "parts": 1,
                                           "end_task": 3, "frames": [1],
                                           "status": SubtaskStatus.starting}
        img_file = os.path.join(self.path, "img1.png")
        img = Image.new("RGB", (800, 600), "#0000ff")
        img.save(img_file)
        task.accept_results("SUBTASK1", [img_file])
        assert task.num_tasks_received == 1
        assert task.collected_file_names[3] == img_file
        preview_img = Image.open(task.preview_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 0, 255)
        preview_img.close()
        preview_img = Image.open(task.preview_task_file_path)
        assert preview_img.getpixel((100, 100)) == (0, 0, 255)
        preview_img.close()

        task.subtasks_given["SUBTASK2"] = {"start_task": 2, "node_id": "NODE 1", "parts": 1,
                                           "end_task": 2, "frames": [1],
                                           "status": SubtaskStatus.starting}
        task.subtasks_given["SUBTASK3"] = {"start_task": 1, "node_id": "NODE 1", "parts": 1,
                                           "end_task": 1, "frames": [1],
                                           "status": SubtaskStatus.starting}
        task.accept_results("SUBTASK2", [img_file])
        task.accept_results("SUBTASK3", [img_file])
        assert task.num_tasks_received == 3
        assert task.total_tasks == 3
        output_file = task.output_file
        assert os.path.isfile(output_file)

        task = self._get_frame_task()
        task.tmp_dir = self.path
        task._accept_client("NODE 1")
        task.subtasks_given["SUBTASK1"] = {"start_task": 3,
                                           "node_id": "NODE 1",
                                           "parts": 1,
                                           "end_task": 3,
                                           "frames": [4, 5],
                                           "status": SubtaskStatus.downloading}
        img_file2 = os.path.join(self.path, "img2.png")
        img.save(img_file2)
        img.close()
        task.accept_results("SUBTASK1", [img_file, img_file2])
        assert task.frames_given["4"][0] == img_file
        assert task.frames_given["5"][0] == img_file2
        assert task.num_tasks_received == 1

    def test_get_output_names(self):
        frame_task = self._get_frame_task(True)
        output_names = frame_task.get_output_names()
        assert len(output_names) == len(frame_task.frames)
        frame_task = self._get_frame_task(False)
        output_names = frame_task.get_output_names()
        assert len(output_names) == 0

    def test_update_frame_preview(self):
        frame_task = self._get_frame_task()
        frame_task.res_x = 10
        frame_task.res_y = 20
        frame_task.total_tasks = 4
        frame_task.frames = [5, 7]
        frame_task.scale_factor = 1
        new_img = Image.new("RGB", (10, 10), (0, 255, 0))
        img_path = self.temp_file_name("image1.png")
        new_img.save(img_path)
        frame_task._update_frame_preview(img_path, 5)

        new_img = Image.new("RGB", (10, 10), (255, 0, 0))
        img_path = self.temp_file_name("image2.png")
        new_img.save(img_path)
        new_img.close()
        frame_task._update_frame_preview(img_path, 5, 2)
        frame_task._update_frame_preview(img_path, 7, 2)
        frame_task._update_frame_preview(img_path, 7, 1, True)

    def test_paste_new_chunk(self):
        task = self._get_frame_task()
        task.res_x = 10
        task.res_y = 20
        task.scale_factor = 1
        preview_path = self.temp_file_name("image1.png")
        with self.assertLogs(logger, level="ERROR") as l:
            assert task._paste_new_chunk("not an image", preview_path, 1, 10) is None
        assert any("Can't generate preview" in log for log in l.output)
        with open(preview_path, 'w') as f:
            f.write("not an image, again not an image")
        with self.assertLogs(logger, level="ERROR") as l:
            assert task._paste_new_chunk("not an image", preview_path, 1, 10) is None
        assert any("Can't add new chunk to preview" in log for log in l.output)
        assert any("Can't generate preview" in log for log in l.output)

        img = Image.new("RGB", (10, 10), (0, 122, 0))
        img.save(preview_path)
        with self.assertLogs(logger, level="ERROR"):
            new_img = task._paste_new_chunk("nota image", preview_path, 1, 10)
        assert isinstance(new_img, Image.Image)
        with self.assertNoLogs(logger, level="ERROR"):
            new_img = task._paste_new_chunk(img, preview_path, 1, 10)
        assert isinstance(new_img, Image.Image)
        img.close()

    def test_mark_task_area(self):
        task = self._get_frame_task()
        task.total_tasks = 4
        task.frames = [3, 4, 6, 7]
        task.scale_factor = 0.5
        task.res_x = 20
        task.res_y = 40
        img = Image.new("RGB", (10, 20), (0, 0, 0))
        task._mark_task_area({'start_task': 2}, img, (121, 0, 0))
        for i in range(10):
            for j in range(20):
                assert img.getpixel((i, j)) == (121, 0, 0)

        task.total_tasks = 2
        task._mark_task_area({'start_task': 2}, img, (0, 13, 0))
        for i in range(10):
            for j in range(20):
                assert img.getpixel((i, j)) == (0, 13, 0)

        task.total_tasks = 8
        task._mark_task_area({'start_task': 2}, img, (0, 0, 201))
        for i in range(10):
            for j in range(10):
                assert img.getpixel((i, j)) == (0, 13, 0)
            for j in range(10, 20):
                assert img.getpixel((i, j)) == (0, 0, 201)
        img.close()

    def test_choose_frames(self):
        task = self._get_frame_task()
        task.total_tasks = 5
        task.frames = [x * 10 for x in range(1, 16)]
        assert task._choose_frames(task.frames, 2, 5) == ([40, 50, 60], 1)

    def test_subtask_frames(self):
        task = self._get_frame_task()
        task.frames = list(range(4))

        frames = task.get_frames_to_subtasks()
        assert len(frames) == 4
        assert all(len(f) == 0 for f in list(frames.values()))

        task.subtasks_given = {
            str(uuid.uuid4()): None,
            str(uuid.uuid4()): {
                'frames': None
            }
        }

        frames = task.get_frames_to_subtasks()
        assert len(frames) == 4
        assert all(len(f) == 0 for f in list(frames.values()))

        task.subtasks_given = {
            str(uuid.uuid4()): {
                'frames': [0, 1]
            },
            str(uuid.uuid4()): {
                'frames': [2, 3]
            }
        }

        frames = task.get_frames_to_subtasks()
        assert len(frames) == 4
        assert all(len(f) == 1 for f in list(frames.values()))

        task.subtasks_given = {
            str(uuid.uuid4()): {
                'frames': [0, 1]
            },
            str(uuid.uuid4()): {
                'frames': [1, 2, 3]
            }
        }

        frames = task.get_frames_to_subtasks()
        assert len(frames) == 4
        assert len(frames[0]) == 1
        assert len(frames[1]) == 2
        assert len(frames[2]) == 1
        assert len(frames[3]) == 1

    def test_update_preview_task_file_path(self):
        task = self._get_frame_task()
        img = Image.new("RGB", (10, 10), (0, 0, 0))
        tmp_path = self.temp_file_name("img.png")
        img.save(tmp_path)
        img.close()
        task._update_preview_task_file_path(tmp_path)
        task = self._get_frame_task(False)
        task._update_preview_task_file_path(tmp_path)

    def test_put_image_together(self):
        task = self._get_frame_task(False)
        task.output_format = "exr"
        task.output_file = self.temp_file_name("output.exr")
        task.res_x = 10
        task.res_y = 20
        exr_1 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile.EXR"
        exr_2 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile2.EXR"
        task.collected_file_names["abc"] = str(exr_1)
        task.collected_file_names["def"] = str(exr_2)
        task._put_image_together()
        img_repr = load_img(task.output_file)
        assert isinstance(img_repr, EXRImgRepr)

    def test_put_frame_together(self):
        task = self._get_frame_task(True)
        task.output_format = "exr"
        task.outfilebasename = "output"
        task.output_file = self.temp_file_name("output.exr")
        task.frames = [3, 5]
        task.total_tasks = 4
        task.res_x = 10
        task.res_y = 20
        exr_1 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile.EXR"
        exr_2 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile2.EXR"
        task.frames_given["5"] = {"abc": str(exr_1), "def": str(exr_2)}
        task._put_frame_together(5, 1)
        out_path = os.path.join(self.path, "output0005.exr")
        img_repr = load_img(out_path)
        assert isinstance(img_repr, EXRImgRepr)


class TestFrameRenderingTaskBuilder(TestDirFixture, LogTestCase):
    def test_calculate_total(self):
        definition = RenderingTaskDefinition()
        definition.optimize_total = True
        definition.total_subtasks = 12
        definition.options = FrameRendererOptions()
        definition.options.use_frames = True
        definition.options.frames = list(range(1, 7))

        builder = FrameRenderingTaskBuilder(root_path=self.path,
                                            dir_manager=DirManager(self.path),
                                            node_name="SOME NODE NAME",
                                            task_definition=definition)

        class Defaults(object):
            def __init__(self, default_subtasks, min_subtasks, max_subtasks):
                self.default_subtasks = default_subtasks
                self.min_subtasks = min_subtasks
                self.max_subtasks = max_subtasks

        defaults = Defaults(13, 3, 33)
        assert builder._calculate_total(defaults) == 6

        definition.options.use_frames = False
        assert builder._calculate_total(defaults) == 13

        definition.optimize_total = False
        assert builder._calculate_total(defaults) == 12

        definition.total_subtasks = None
        assert builder._calculate_total(defaults) == 13

        definition.total_subtasks = 0
        assert builder._calculate_total(defaults) == 13

        definition.total_subtasks = 1
        assert builder._calculate_total(defaults) == 13

        definition.total_subtasks = 2
        assert builder._calculate_total(defaults) == 13

        definition.total_subtasks = 3
        assert builder._calculate_total(defaults) == 3

        definition.total_subtasks = 34
        assert builder._calculate_total(defaults) == 13

        definition.total_subtasks = 33
        assert builder._calculate_total(defaults) == 33

        definition.options.use_frames = True

        definition.total_subtasks = None
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 6

        definition.total_subtasks = 0
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 6

        definition.total_subtasks = 1
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 1

        definition.total_subtasks = 2
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 2

        definition.total_subtasks = 3
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 3

        definition.total_subtasks = 6
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 6

        definition.total_subtasks = 12
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 12

        definition.total_subtasks = 4
        with self.assertLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 3

        definition.total_subtasks = 13
        with self.assertLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 12

        definition.total_subtasks = 17
        with self.assertLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 12

        definition.total_subtasks = 18
        with self.assertNoLogs(logger, level="WARNING"):
            assert builder._calculate_total(defaults) == 18


class TestFramesConversion(unittest.TestCase):
    def test_frames_to_string(self):
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([1, 4, 3, 2]), "1-4")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([1]), "1")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string(list(range(10))), "0-9")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string(list(range(13, 16)) + list(range(10))),
                         "0-9;13-15")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([1, 3, 4, 5, 10, 11]), '1;3-5;10-11')
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([0, 5, 10, 15]), '0;5;10;15')
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([]), "")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string(["abc", "5"]), "")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string(["1", "5"]), "1;5")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string(["5", "2", "1", "3"]), "1-3;5")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([-1]), "")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string([2, 3, -1]), "")
        self.assertEqual(FrameRenderingTaskBuilder
                         .frames_to_string("ABC"), "")

    def test_string_to_frames(self):
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('1-4'), list(range(1, 5)))
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('5-8;1-3'), [1, 2, 3, 5, 6, 7, 8])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('1 - 4'), list(range(1, 5)))
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('0-9; 13-15'),
                         list(range(10)) + list(range(13, 16)))
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('0-15,5;23'), [0, 5, 10, 15, 23])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('0-15,5;23-25;26'),
                         [0, 5, 10, 15, 23, 24, 25, 26])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('abc'), [])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('0-15,5;abc'), [])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames(0), [])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('5-8;1-2-3'), [])
        self.assertEqual(FrameRenderingTaskBuilder
                         .string_to_frames('1-100,2,3'), [])
