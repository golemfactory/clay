import time

from mock import Mock

from golem.tools.testdirfixture import TestDirFixture

from gnr.task.renderingtask import RenderingTask


class TestRenderingTask(TestDirFixture):

    def test_total_tasks(self):
        files_ = self.additional_dir_content([2])
        task = RenderingTask("NODE_ABC", "XYZ", "10.10.10.10", 40102, "KEY", "ENV", time.time() + 60 * 5,
                             60,  files_[0], [], self.path, files_[1], 7, 30, 30, "out", "out2", ".png",
                             self.path, 1000, 30, None)
        assert isinstance(task, RenderingTask)
        assert task.total_tasks == 7
        task.redundancy = 3
        assert task.total_tasks == 21
        task.subtasks_given["xyz"] = {'start_task': 1}
        assert task._get_part_img_size("xyz", None) == (0, 0, 30, 4)
        task.subtasks_given["abc"] = {'start_task': 14}
        assert task._get_part_img_size("abc", None) == (0, 16, 30, 20)

        img_mock = Mock()
        task._mark_task_area(task.subtasks_given["xyz"], img_mock, "pink")
        pixel_list = [x[0][0] for x in img_mock.putpixel.call_args_list]
        img_mock.putpixel.assert_called_with((29, 3), "pink")
        for i in range(30):
            for j in range(4):
                assert (i, j) in pixel_list

        img_mock2 = Mock()
        task._mark_task_area(task.subtasks_given["abc"], img_mock2, "magenta")
        img_mock2.putpixel.assert_called_with((29, 20), "magenta")
        pixel_list = [x[0][0] for x in img_mock2.putpixel.call_args_list]
        for i in range(30):
            for j in range(17, 21):
                assert (i, j) in pixel_list


