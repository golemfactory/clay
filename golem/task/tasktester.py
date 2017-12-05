import logging

from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task
from golem.task.taskcomputer import PyTestTaskThread

logger = logging.getLogger("golem.task")


class TaskTester(LocalComputer):
    TESTER_WARNING = "Task not tested properly"
    TESTER_SUCCESS = "Test task computation success!"

    # TODO I think there should be Task, not CoreTask type
    # but Task doesn't have query_extra_data_for_test_task method
    def __init__(self, task: Task, root_path, success_callback, error_callback):
        super(TaskTester, self).__init__(task, root_path, success_callback, error_callback,
                                         task.query_extra_data_for_test_task, True,
                                         TaskTester.TESTER_WARNING, TaskTester.TESTER_SUCCESS)

    def _get_task_thread(self, ctd):
        # ctd: ComputeTaskDef
        if ctd['docker_images']:
            return LocalComputer._get_task_thread(self, ctd)
        else:
            return PyTestTaskThread(self,
                                    ctd['subtask_id'],
                                    ctd['working_directory'],
                                    ctd['src_code'],
                                    ctd['extra_data'],
                                    ctd['short_description'],
                                    self.test_task_res_path,
                                    self.tmp_dir,
                                    0)

    def computation_success(self, task_thread):
        time_spent = self._get_time_spent()
        res, est_mem = task_thread.result
        after_test_data = self.task.after_test(res, self.tmp_dir)
        self.success_callback(res, est_mem, time_spent,
                              after_test_data=after_test_data)

    def is_success(self, task_thread):
        if task_thread.error or (not task_thread.result):
            return False
        try:
            res, _ = task_thread.result
        except (ValueError, TypeError):
            task_thread.error = "Wrong result format"
            return False
        return res and res.get("data")
