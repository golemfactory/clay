import logging

from golem.task.localcomputer import LocalComputer
from golem.task.taskbase import Task

logger = logging.getLogger("golem.task")


class TaskTester(LocalComputer):
    TESTER_WARNING = "Task not tested properly"
    TESTER_SUCCESS = "Test task computation success!"

    # TODO I think there should be Task, not CoreTask type
    # but Task doesn't have query_extra_data_for_test_task method
    # Issue: #1355
    # pylint: disable=too-many-arguments
    def __init__(self, task: Task, environments_manager, root_path,
                 success_callback, error_callback) -> None:
        super(TaskTester, self).__init__(
            root_path=root_path,
            environments_manager=environments_manager,
            success_callback=success_callback,
            error_callback=error_callback,
            get_compute_task_def=task.query_extra_data_for_test_task,
            check_mem=True,
            comp_failed_warning=TaskTester.TESTER_WARNING,
            comp_success_message=TaskTester.TESTER_SUCCESS,
            resources=task.get_resources())
        self.task = task

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
