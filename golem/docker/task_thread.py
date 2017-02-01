import logging
import os

import requests
from golem.docker.job import DockerJob
from golem.task.taskthread import TaskThread
from golem.vm.memorychecker import MemoryChecker

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    pass


class DockerTaskThread(TaskThread):

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    docker_manager = None

    def __init__(self, task_computer, subtask_id, docker_images,
                 orig_script_dir, src_code, extra_data, short_desc,
                 res_path, tmp_path, timeout, check_mem=False):

        if not docker_images:
            raise AttributeError("docker images is None")
        super(DockerTaskThread, self).__init__(
            task_computer, subtask_id, orig_script_dir, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)

        # Find available image
        self.image = None
        logger.debug("Chechking docker images %s", docker_images)
        for img in docker_images:
            if img.is_available():
                self.image = img
                break

        self.job = None
        self.mc = None
        self.check_mem = check_mem

    def run(self):
        if not self.image:
            self._fail("None of the Docker images is available")
            self._cleanup()
            return
        try:
            if self.use_timeout and self.task_timeout < 0:
                raise TimeoutException
            work_dir = os.path.join(self.tmp_path, "work")
            output_dir = os.path.join(self.tmp_path, "output")

            if not os.path.exists(work_dir):
                os.mkdir(work_dir)
            if not os.path.exists(output_dir):
                os.mkdir(output_dir)

            if self.docker_manager:
                host_config = self.docker_manager.container_host_config
            else:
                host_config = None

            with DockerJob(self.image, self.src_code, self.extra_data,
                           self.res_path, work_dir, output_dir,
                           host_config=host_config) as job:
                self.job = job
                if self.check_mem:
                    self.mc = MemoryChecker()
                    self.mc.start()
                self.job.start()
                exit_code = self.job.wait()
                # Get stdout and stderr
                stdout_file = os.path.join(output_dir, self.STDOUT_FILE)
                stderr_file = os.path.join(output_dir, self.STDERR_FILE)
                self.job.dump_logs(stdout_file, stderr_file)

                if self.mc:
                    estm_mem = self.mc.stop()
                if exit_code == 0:
                    # TODO: this always returns file, implement returning data
                    out_files = []
                    for root, _, files in os.walk(output_dir):
                        for name in files:
                            out_files.append(os.path.join(root, name))
                    self.result = {"data": out_files, "result_type": 1}
                    if self.check_mem:
                        self.result = (self.result, estm_mem)
                    self.task_computer.task_computed(self)
                else:
                    with open(stderr_file, 'r') as f:
                        logger.warning('Task stderr:\n%s', f.read())
                    self._fail("Subtask computation failed " +
                               "with exit code {}".format(exit_code))
        except (requests.exceptions.ReadTimeout, TimeoutException) as exc:
            if self.use_timeout:
                self._fail("Task timed out after {:.1f}s".
                           format(self.time_to_compute))
            else:
                self._fail(exc)
        except Exception as exc:
            self._fail(exc)
        finally:
            self._cleanup()

    def get_progress(self):
        # TODO: make the container update some status file?
        return 0.0

    def end_comp(self):
        try:
            self.job.kill()
        except AttributeError:
            pass
        except requests.exceptions.BaseHTTPError:
            if self.docker_manager:
                self.docker_manager.recover_vm_connectivity(self.job.kill)

    def _cleanup(self):
        if self.mc:
            self.mc.stop()
