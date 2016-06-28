import logging
import os

import requests

from golem.docker.job import DockerJob
from golem.task.taskthread import TaskThread
from golem.vm.memorychecker import MemoryChecker

logger = logging.getLogger(__name__)


class DockerTaskThread(TaskThread):

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    container_host_config = None

    def __init__(self, task_computer, subtask_id, docker_images,
                 orig_script_dir, src_code, extra_data, short_desc,
                 res_path, tmp_path, timeout, check_mem=False):

        super(DockerTaskThread, self).__init__(
            task_computer, subtask_id, orig_script_dir, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)

        assert docker_images
        # Find available image
        self.image = None
        for img in docker_images:
            if img.is_available():
                self.image = img
                break

        self.job = None
        self.check_mem = check_mem

    def _fail(self, error_obj):
        logger.error("Task computing error: {}".format(error_obj))
        self.error = True
        self.error_msg = str(error_obj)
        self.done = True
        self.task_computer.task_computed(self)

    def run(self):
        if not self.image:
            self._fail("None of the Docker images is available")
            return
        try:
            work_dir = os.path.join(self.tmp_path, "work")
            output_dir = os.path.join(self.tmp_path, "output")

            if not os.path.exists(work_dir):
                os.mkdir(work_dir)
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)

            with DockerJob(self.image, self.src_code, self.extra_data,
                           self.res_path, work_dir, output_dir,
                           host_config=self.container_host_config,
                           container_log_level=0) as job:
                self.job = job
                if self.check_mem:
                    mc = MemoryChecker()
                    mc.start()
                self.job.start()
                if self.use_timeout:
                    exit_code = self.job.wait(self.task_timeout)
                else:
                    exit_code = self.job.wait()

                # Get stdout and stderr
                stdout_file = os.path.join(output_dir, self.STDOUT_FILE)
                stderr_file = os.path.join(output_dir, self.STDERR_FILE)
                self.job.dump_logs(stdout_file, stderr_file)

                if self.check_mem:
                    estm_mem = mc.stop()
                if exit_code == 0:
                    # TODO: this always returns file, implement returning data
                    # TODO: this only collects top-level files, what if there
                    # are output files in subdirs?
                    out_files = [os.path.join(output_dir, f)
                                 for f in os.listdir(output_dir)]
                    out_files = filter(lambda f: os.path.isfile(f), out_files)
                    self.result = {"data": out_files, "result_type": 1}
                    if self.check_mem:
                        self.result = (self.result, estm_mem)
                    self.task_computer.task_computed(self)
                else:
                    self._fail("Subtask computation failed " +
                               "with exit code {}".format(exit_code))
        except requests.exceptions.ReadTimeout as exc:
            if self.use_timeout:
                self._fail("Task timed out after {:.1f}s".
                           format(self.task_timeout))
            else:
                self._fail(exc)
        except Exception as exc:
            self._fail(exc)

    def get_progress(self):
        # TODO: make the container update some status file?
        return 0.0

    def end_comp(self):
        pass

    def check_timeout(self):
        pass
