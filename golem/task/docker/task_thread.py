import logging
import os

import requests

from golem.task.docker.job import DockerJob
from golem.task.taskthread import TaskThread


logger = logging.getLogger(__name__)


class DockerTaskThread(TaskThread):

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    def __init__(self, task_computer, subtask_id, docker_images,
                 working_directory, src_code, extra_data, short_desc,
                 res_path, tmp_path, timeout):
        super(DockerTaskThread, self).__init__(
            task_computer, subtask_id, working_directory, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)

        assert docker_images
        # Find available image
        self.image = None
        for img in docker_images:
            if img.is_available():
                self.image = img
                break
        self.job = None

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
            params = self.extra_data.copy()
            with DockerJob(self.image, self.src_code, params,
                           self.working_directory,
                           self.res_path, self.tmp_path) as job:
                self.job = job
                self.job.start()
                if self.use_timeout:
                    exit_code = self.job.wait(self.task_timeout)
                else:
                    exit_code = self.job.wait()

                # Get stdout and stderr
                stdout_file = os.path.join(self.tmp_path, self.STDOUT_FILE)
                stderr_file = os.path.join(self.tmp_path, self.STDERR_FILE)
                self.job.dump_logs(stdout_file, stderr_file)

                if exit_code == 0:
                    # TODO: this always returns file, implement returning data
                    # TODO: this only collects top-level files, what if there
                    # are output files in subdirs?
                    out_files = [os.path.join(self.tmp_path, f)
                                 for f in os.listdir(self.tmp_path)]
                    out_files = filter(lambda f: os.path.isfile(f), out_files)
                    self.result = {"data": out_files, "result_type": 1}
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
