import logging
import time

from golem.task.localcomputer import LocalComputer


logger = logging.getLogger("gnr.benchmarks")


class BenchmarkRunner(LocalComputer):
    RUNNER_WARNING = "Failed to compute benchmark"
    RUNNER_SUCCESS = "Benchmark computed successfully"

    def __init__(self, task, root_path, success_callback, error_callback, benchmark):
        LocalComputer.__init__(self, task, root_path, success_callback, error_callback,
                               # ugly lambda, should think of something prettier
                               lambda: task.query_extra_data(10000).ctd,
                               True, BenchmarkRunner.RUNNER_WARNING,
                               BenchmarkRunner.RUNNER_SUCCESS)
        # probably this could be done differently
        self.benchmark = benchmark
        self.start_time = None
        self.end_time = None
        
    def _get_task_thread(self, ctd):
        if ctd.docker_images:
            return LocalComputer._get_task_thread(self, ctd)
        else:
            raise Exception("No docker container found")

    def start(self):
        self.start_time = time.time()
        logger.debug("Started at {}".format(self.start_time))
        LocalComputer.run(self)

    def run(self):
        self.start()
        if self.tt:
            self.tt.join()
    
    def task_computed(self, task_thread):
        self.end_time = time.time()
        logger.debug("Ended at {}".format(self.end_time))
        if task_thread.result:
            res, _ = task_thread.result
            if res and res.get("data"):
                print res["data"]
                if self.benchmark.verify_result(res["data"]):
                    self.success_callback(self.benchmark.normalization_constant / (self.end_time - self.start_time))
                    return

        logger_msg = self.comp_failed_warning
        if task_thread.error_msg:
            logger_msg += " " + task_thread.error_msg
        logger.warning(logger_msg)
        self.error_callback(task_thread.error_msg)
