import logging

from golem.task.localcomputer import LocalComputer
from golem.task.taskcomputer import PyTestTaskThread

logger = logging.getLogger("golem.task")


class TaskTester(LocalComputer):
    TESTER_WARNING = "Task not tested properly"
    TESTER_SUCCESS = "Test task computation success!"

    def __init__(self, task, root_path, success_callback, error_callback):
        LocalComputer.__init__(self, task, root_path, success_callback, error_callback,
                               task.query_extra_data_for_test_task, True, TaskTester.TESTER_WARNING,
                               TaskTester.TESTER_SUCCESS)

    def _get_task_thread(self, ctd):
        if ctd.docker_images:
            return LocalComputer._get_task_thread(self, ctd)
        else:
            return PyTestTaskThread(self,
                                    ctd.subtask_id,
                                    ctd.working_directory,
                                    ctd.src_code,
                                    ctd.extra_data,
                                    ctd.short_description,
                                    self.test_task_res_path,
                                    self.tmp_dir,
                                    0)

    def task_computed(self, task_thread):
        if (not task_thread.error) and task_thread.result:
            res, est_mem = task_thread.result
            if res and res.get("data"):
                warnings = self.task.after_test(res, self.tmp_dir)
                self.success_callback(res, est_mem, msg=warnings)
                return

        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(task_thread.error_msg)
