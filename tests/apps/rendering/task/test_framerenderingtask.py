import os
import unittest
import uuid
from pathlib import Path

from golem_messages.factories.datastructures import p2p as dt_p2p_factory

from apps.core.task.coretask import CoreTaskTypeInfo
from apps.core.task.coretaskstate import Options
from apps.rendering.resources.imgrepr import load_img, EXRImgRepr, OpenCVImgRepr
from apps.rendering.task.framerenderingtask import get_frame_name, \
    FrameRenderingTask, FrameRenderingTaskBuilder, FrameRendererOptions, logger
from apps.rendering.task.renderingtask import MIN_PIXELS_PER_SUBTASK
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.assertlogs import LogTestCase
from golem.tools.testdirfixture import TestDirFixture


class FrameRenderingTaskMock(FrameRenderingTask):
    class ENVIRONMENT_CLASS(object):
        docker_images = []

        def get_id(self):
            return "TEST"

    def query_extra_data(*args, **kwargs):
        pass

    def query_extra_data_for_test_task(self):
        pass


class TestFrameRenderingTask(TestDirFixture, LogTestCase):
    def _get_frame_task(self, use_frames=True, num_tasks=3):
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
        rt.timeout = 3600
        rt.subtask_timeout = 600
        rt.estimated_memory = 1000
        rt.max_price = 15
        rt.subtasks_count = num_tasks
        task = FrameRenderingTaskMock(
            owner=dt_p2p_factory.Node(node_name="ABC", ),
            task_definition=rt,
            root_path=self.path,
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
        task.accept_client("NODE 1", 'oh')
        task.tmp_dir = self.path
        task.subtasks_given["SUBTASK1"] = {"start_task": 3, "node_id": "NODE 1",
                                           "parts": 1, "frames": [1],
                                           "status": SubtaskStatus.starting}
        img_file = os.path.join(self.path, "img1.png")
        img = OpenCVImgRepr.empty(800, 600, color=(0, 0, 255))
        img.save(img_file)
        task.accept_results("SUBTASK1", [img_file])
        assert task.num_tasks_received == 1
        assert task.collected_file_names[3] == img_file
        preview_img = OpenCVImgRepr.from_image_file(task.preview_file_path)
        assert preview_img.get_pixel((100, 100)) == (0, 0, 255)
        preview_img = OpenCVImgRepr.from_image_file(task.preview_task_file_path)
        assert preview_img.get_pixel((100, 100)) == (0, 0, 255)
        task.subtasks_given["SUBTASK2"] = {"start_task": 2, "node_id": "NODE 1",
                                           "parts": 1,
                                           "frames": [1],
                                           "status": SubtaskStatus.starting}
        task.subtasks_given["SUBTASK3"] = {"start_task": 1, "node_id": "NODE 1",
                                           "parts": 1,
                                           "frames": [1],
                                           "status": SubtaskStatus.starting}
        task.accept_results("SUBTASK2", [img_file])
        task.accept_results("SUBTASK3", [img_file])
        assert task.num_tasks_received == 3
        assert task.get_total_tasks() == 3
        output_file = task.output_file
        assert os.path.isfile(output_file)

        task = self._get_frame_task()
        task.tmp_dir = self.path
        task.accept_client("NODE 1", 'oh')
        task.subtasks_given["SUBTASK1"] = {"start_task": 3,
                                           "node_id": "NODE 1",
                                           "parts": 1,
                                           "frames": [4, 5],
                                           "status": SubtaskStatus.downloading}
        img_file2 = os.path.join(self.path, "img2.png")
        img.save(img_file2)
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
        frame_task = self._get_frame_task(num_tasks=4)
        frame_task.res_x = 10
        frame_task.res_y = 20
        frame_task.frames = [5, 7]
        frame_task.scale_factor = 1
        new_img = OpenCVImgRepr.empty(10, 10, color=(0, 255, 0))
        img_path = self.temp_file_name("image1.png")
        new_img.save(img_path)
        frame_task._update_frame_preview(img_path, 5)
        new_img = OpenCVImgRepr.empty(10, 10, color=(255, 0, 0))
        img_path = self.temp_file_name("image2.png")
        new_img.save(img_path)
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

        img = OpenCVImgRepr.empty(10, 10, color=(0, 122, 0))
        img.save(preview_path)
        with self.assertLogs(logger, level="ERROR"):
            new_img = task._paste_new_chunk("nota image", preview_path, 1, 10)
        assert isinstance(new_img, OpenCVImgRepr)

        with self.assertLogs(logger, level="ERROR"):
            new_img = task._paste_new_chunk(img, preview_path, 1, 10)
        assert isinstance(new_img, OpenCVImgRepr)

        img = OpenCVImgRepr.empty(10, 20, color=(0, 122, 0))
        img.save(preview_path)
        with self.assertNoLogs(logger, level="ERROR"):
            new_img = task._paste_new_chunk(img, preview_path, 1, 10)
        assert isinstance(new_img, OpenCVImgRepr)

    def test_mark_task_area(self):
        task = self._get_frame_task(num_tasks=4)
        task.frames = [3, 4, 6, 7]
        task.scale_factor = 0.5
        task.res_x = 20
        task.res_y = 40
        img = OpenCVImgRepr.empty(10, 20, color=(0, 0, 0))
        task._mark_task_area({'start_task': 2}, img, (121, 0, 0))
        for i in range(10):
            for j in range(20):
                assert img.get_pixel((i, j)) == (121, 0, 0)

        task.task_definition.subtasks_count = 2
        task._mark_task_area({'start_task': 2}, img, (0, 13, 0))
        for i in range(10):
            for j in range(20):
                assert img.get_pixel((i, j)) == (0, 13, 0)

        task.task_definition.subtasks_count = 8
        task._mark_task_area({'start_task': 2}, img, (0, 0, 201))
        for i in range(10):
            for j in range(10):
                assert img.get_pixel((i, j)) == (0, 13, 0)
            for j in range(10, 20):
                assert img.get_pixel((i, j)) == (0, 0, 201)

    def test_choose_frames(self):
        task = self._get_frame_task(num_tasks=5)
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
        img = OpenCVImgRepr.empty(10, 10, color=(0, 0, 0))
        tmp_path = self.temp_file_name("img.png")
        img.save(tmp_path)
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
        img_repr.close()

    def test_put_frame_together(self):
        task = self._get_frame_task(use_frames=True, num_tasks=4)
        task.output_format = "exr"
        task.outfilebasename = "output"
        task.output_file = self.temp_file_name("output.exr")
        task.frames = [3, 5]
        task.res_x = 10
        task.res_y = 20
        exr_1 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile.EXR"
        exr_2 = Path(__file__).parent.parent.parent / "rendering" / "resources" / "testfile2.EXR"
        task.frames_given["5"] = {"abc": str(exr_1), "def": str(exr_2)}
        task._put_frame_together(5, 1)
        out_path = os.path.join(self.path, "output0005.exr")
        img_repr = load_img(out_path)
        assert isinstance(img_repr, EXRImgRepr)
        img_repr.close()

    def test_get_subtask_for_multiple_subtask_per_frame(self):
        task = self._get_frame_task(True, 18)
        print(task.frames_subtasks)
        assert task.get_subtasks(4) == {}
        task.frames_subtasks["4"][0] = "abc"
        task.frames_subtasks["4"][1] = "def"
        task.subtasks_given["abc"] = {"ABC": 3}
        task.subtasks_given["def"] = {"DEF": 4}
        states = task.get_subtasks(4)
        assert states["abc"]["ABC"] == 3
        assert states["def"]["DEF"] == 4
        assert len(states) == 2


class TestBuildDefinition(unittest.TestCase):
    def setUp(self):
        self.tti = CoreTaskTypeInfo("TESTTASK", RenderingTaskDefinition,
                                    Options,
                                    FrameRenderingTaskBuilder)
        self.tti.output_file_ext = 'txt'

    @staticmethod
    def _make_dict(
            *,
            frame_count: int = 1,
            pixel_height: int = MIN_PIXELS_PER_SUBTASK,
            subtasks_count: int = 1,
    ):
        assert frame_count > 0
        if frame_count == 1:
            frames = "1"
        else:
            frames = f"1-{frame_count}"

        return {
            "bid": 0,
            "name": "foo",
            "options": {
                "format": "PNG",
                "frame_count": frame_count,
                "frames": frames,
                "output_path": "/tmp/foo",
                "resolution": [MIN_PIXELS_PER_SUBTASK, pixel_height],
            },
            "resources": ["foo.txt"],
            "subtask_timeout": "0:01:00",
            "subtasks_count": subtasks_count,
            "timeout": "0:01:00",
        }

    def test_subtasks_count(self):
        # sort tests by (frame_count, pixel_height, subtasks_count)
        tests = [
            {
                "make_dict_kwargs": {},
                "expected_subtasks_count": 1,
            },
            {
                "make_dict_kwargs": {
                    "pixel_height": 5,
                },
                "expected_throw": True,  # image too small
            },
            {
                "make_dict_kwargs": {
                    "pixel_height": 15,
                    "subtasks_count": 2,
                },
                "expected_subtasks_count": 1,
            },
            {
                "make_dict_kwargs": {
                    "frame_count": 6,
                    "subtasks_count": 3,
                },
                "expected_subtasks_count": 3,
            },
            {
                "make_dict_kwargs": {
                    "frame_count": 6,
                    "subtasks_count": 4,
                },
                "expected_subtasks_count": 4,
            },
            {
                "make_dict_kwargs": {
                    "frame_count": 6,
                    "pixel_height": 768,
                    "subtasks_count": 50,
                },
                "expected_subtasks_count": 48,
            },
            {
                "make_dict_kwargs": {
                    "frame_count": 6,
                    "pixel_height": 768,
                    "subtasks_count": 457,
                },
                "expected_subtasks_count": 456,
            },
        ]
        failures = []
        for test in tests:
            task_dict = self._make_dict(**test["make_dict_kwargs"])
            definition = None
            thrown_exception = None

            try:
                definition = FrameRenderingTaskBuilder.build_definition(
                    self.tti, task_dict)
            except Exception as e:  # pylint: disable=broad-except
                thrown_exception = e

            if thrown_exception is not None and \
                    not test.get("expected_throw", False):
                test["thrown_exception"] = thrown_exception
                failures.append(test)

            if definition and (
                    definition.subtasks_count
                    != test["expected_subtasks_count"]):
                test["actual_subtasks_count"] = definition.subtasks_count
                failures.append(test)
        assert failures == []


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
