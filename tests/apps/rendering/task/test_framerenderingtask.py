import os

from PIL import Image

from golem.resource.dirmanager import DirManager
from golem.task.taskstate import SubtaskStatus
from golem.tools.testdirfixture import TestDirFixture

from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from apps.rendering.task.framerenderingtask import (get_frame_name, FrameRenderingTask,
                                                    FrameRendererOptions)


class FrameRenderingTaskMock(FrameRenderingTask):
    class ENVIRONMENT_CLASS(object):
        main_program_file = None
        docker_images = []

        def get_id(self):
            return "TEST"

    def __init__(self, main_program_file, *args, **kwargs):
        self.ENVIRONMENT_CLASS.main_program_file = main_program_file
        super(FrameRenderingTaskMock, self).__init__(*args, **kwargs)


class TestFrameRenderingTask(TestDirFixture):

    def _get_frame_task(self, use_frames=True):
        files_ = self.additional_dir_content([3])
        rt = RenderingTaskDefinition()
        rt.options = FrameRendererOptions()
        rt.options.use_frames = use_frames
        rt.options.frames = range(6)
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
        task.subtasks_given["SUBTASK1"] = {"start_task": 3, "node_id": "NODE 1", "parts": 1,
                                           "end_task": 3, "frames": [4, 5]}
        img_file2 = os.path.join(self.path, "img2.png")
        img_2 = img.save(img_file2)
        img.close()
        task.accept_results("SUBTASK1", [img_file, img_file2])
        assert task.frames_given["4"][0] == img_file
        assert task.frames_given["5"][0] == img_file2
