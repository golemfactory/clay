import hashlib
import logging
import os
from typing import List, Dict

import requests
import json

from golem.docker.job import DockerJob
from golem.task.taskbase import ResultType
from golem.task.taskthread import TaskThread
from golem.vm.memorychecker import MemoryChecker

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    pass

# TODO change the way OUTPUT_DIR and WORK_DIR are handled
# now there is duplication of declarations in DockerJob and here
# plus, there is GOLEM_BASE_PATH hardcoded here
class DockerTaskThread(TaskThread):

    GOLEM_BASE_PATH = "/golem"

    OUTPUT_DIR = "output"
    WORK_DIR = "work"
    RESOURCES_DIR = "resources"

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    # These files are located in the work dir, they are updated by job.py
    # it contains list of incoming messages in json
    MESSAGES_IN_DIR = os.path.join(WORK_DIR, "messages_in")
    # it contains list outcoming messages in json
    MESSAGES_OUT_DIR = os.path.join(WORK_DIR, "messages_out")

    docker_manager = None

    def __init__(self,
                 task_computer: 'TaskComputer',
                 subtask_id: str,
                 docker_images: 'List[DockerImage]',
                 _: str, # orig_script_dir: str - it was used in golem vm, now dead
                 src_code: str,
                 extra_data: Dict,
                 short_desc: str,
                 res_path: str,
                 tmp_path: str,
                 timeout,
                 check_mem=False):

        if not docker_images:
            raise AttributeError("docker images is None")
        super().__init__(task_computer,
                         subtask_id,
                         "",  # it wsa orig_script_dir
                         src_code,
                         extra_data,
                         short_desc,
                         res_path,
                         tmp_path,
                         timeout)

        # Find available image
        self.image = None
        logger.debug("Checking docker images %s", docker_images)
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
            work_dir = os.path.join(self.tmp_path, self.WORK_DIR)
            output_dir = os.path.join(self.tmp_path, self.OUTPUT_DIR)

            if not os.path.exists(work_dir):
                os.makedirs(work_dir)
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)

            messages_dirs = [os.path.join(self.tmp_path, self.MESSAGES_IN_DIR),
                             os.path.join(self.tmp_path, self.MESSAGES_OUT_DIR)]
            for m in messages_dirs:
                if not os.path.exists(m):
                    os.mkdir(m)

            paths_params = {k: os.path.join(self.GOLEM_BASE_PATH, v) for k, v in
                            {
                                "RESOURCES_DIR": self.RESOURCES_DIR,
                                "WORK_DIR": self.WORK_DIR,
                                "OUTPUT_DIR": self.OUTPUT_DIR,
                                "MESSAGES_IN_DIR": self.MESSAGES_IN_DIR,
                                "MESSAGES_OUT_DIR": self.MESSAGES_OUT_DIR
                            }.items()}
            self.extra_data.update(paths_params)

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
                    self.result = {"data": out_files, "result_type": ResultType.FILES}
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
        return 0.0

    # TODO make the structure of msgs_decoded explicit somewhere
    # instead of "content": ..., "filename": ... hardcoded here
    def check_for_new_messages(self) -> List[Dict]:
        """ Check is the script produced any new messages
        :return: list containing list of messages, each of which is a dict
        """
        if not self.job:
            return [{}]
        msgs = self.job.read_work_files(self.MESSAGES_OUT_DIR)
        msgs_decoded = []
        for filename, content in msgs.items():
            try:
                msgs_decoded.append({
                    "content": json.loads(content),
                    "filename": filename
                })
            except ValueError:
                msgs_decoded.append({})
                logger.warning("ValueError during decoding message %r", str(content))  # noqa

        # cleaning messages files, to not read multiple times the same content
        self.job.clean_work_files(self.MESSAGES_OUT_DIR)

        return msgs_decoded

    def receive_message(self, data: Dict):
        """
        Takes a message from network and puts it in new file in MESSAGES_IN_DIR
        :param data: Message data
        :return:
        """
        # TODO consider moving hash somewhere else
        # although it is not very important
        # messages names don't matter at all
        # it's just that they should be unique
        HASH = lambda x: hashlib.md5(x.encode()).hexdigest()
        if self.job:
            data_dump = json.dumps(data)

            msg_filename = HASH(data_dump)
            msg_path = os.path.join(self.MESSAGES_IN_DIR, msg_filename)
            self.job.write_work_file(msg_path, data_dump, options="w")
        else:
            logger.warning("There is currently no job to receive message")

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
