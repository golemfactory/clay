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
            message = None
            if res and res.get("data"):
                missing_files = self.task.after_test(res, self.tmp_dir)
                if missing_files:
                    message = u"Additional data is missing:\n"
                    for w in missing_files:
                        message += u"    {}\n".format(w)
                    message += u"\nMake sure you added all required files to resources."
                self.success_callback(res, est_mem, msg=message)
                return

        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(task_thread.error_msg)
