import time

from golem.tools.testdirfixture import TestDirFixture

from gnr.task.framerenderingtask import FrameRenderingTask


class TestFrameRenderingTask(TestDirFixture):
    def setUp(self):
        super(TestFrameRenderingTask, self).setUp()
        self.files = self.additional_dir_content([2])

    def _get_init_params(self):
        return ("NODE_ABC", "XYZ", "10.10.10.10", 40102, "KEY", "ENV", time.time() + 60 * 5,
                60,  self.files[0], [], self.path, self.files, 7, 1, 30, 30, "out", "out2", ".png",
                self.path, 1000, True, range(1, 11), 30, None)

    def test_total_tasks(self):
        task = FrameRenderingTask(*self._get_init_params())
        assert isinstance(task, FrameRenderingTask)
        assert task.total_tasks == 7
        task.redundancy = 3
        assert task.total_tasks == 21

        task.num_subtasks = 5
        assert task.total_tasks == 15
        assert task._choose_frames(1) == ([1, 2], 1)
        assert task._choose_frames(2) == ([1, 2], 1)
        assert task._choose_frames(3) == ([1, 2], 1)
        assert task._choose_frames(4) == ([3, 4], 1)
        assert task._choose_frames(15) == ([9, 10], 1)

        task.num_subtasks = 30
        assert task.total_tasks == 90
        for i in range(1, 10):
            assert task._choose_frames(i) == ([1], 3)
        for i in range(10, 19):
            assert task._choose_frames(i) == ([2], 3)

        task.num_subtasks = 10
        for i in range(1, 3):
            task._choose_frames(i) == ([1], 1)
        for i in range(4, 6):
            task._choose_frames(i) == ([2], 1)
        for i in range(28, 30):
            task._choose_frames(i) == ([10], 1)


