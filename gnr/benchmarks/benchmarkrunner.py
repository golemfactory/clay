import logging
import time

from gnr.task.localcomputer import LocalComputer

from golem.task.taskcomputer import PyTestTaskThread


logger = logging.getLogger(__name__)


class BenchmarkRunner(LocalComputer):
    RUNNER_WARNING = "Failed to compute benchmark"
    RUNNER_SUCCESS = "Benchmark computed successfully"

    def __init__(self, task, root_path, success_callback, error_callback, benchmark):
        LocalComputer.__init__(self, task, root_path, success_callback, error_callback,
                               # ugly lambda, should think of something prettier
                               lambda: task.query_extra_data(10000), 
                               True, BenchmarkRunner.RUNNER_WARNING,
                               BenchmarkRunner.RUNNER_SUCCESS)
        # probably this could be done differently
        self.benchmark = benchmark
        
    def _get_task_thread(self, ctd):
        if ctd.docker_images:
            return LocalComputer._get_task_thread(self, ctd)
        else:
            #TODO not allow running tasks outside docker?
            return PyTestTaskThread(self,
                                    ctd.subtask_id,
                                    ctd.working_directory,
                                    ctd.src_code,
                                    ctd.extra_data,
                                    ctd.short_description,
                                    self.test_task_res_path,
                                    self.tmp_dir,
                                    0)
    
    def run(self):
        self.start_time = time.time()
        logger.debug("Started at {}".format(self.start_time))
        LocalComputer.run(self)
    
    def task_computed(self, task_thread):
        self.end_time = time.time()
        logger.debug("Ended at {}".format(self.end_time))
        if task_thread.result:
            res, _ = task_thread.result
            if res and res.get("data"):
                print res["data"]
                if self.benchmark.verify_result(res["data"]):
                    self.success_callback(self.end_time - self.start_time)
                    return

        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(task_thread.error_msg)
    