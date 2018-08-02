import hashlib
import json
import logging
import os
from pathlib import Path
from typing import ClassVar, Optional, TYPE_CHECKING, List, Dict

import requests
from golem.docker.job import DockerJob
from golem.task.taskbase import ResultType
from golem.task.taskthread import TaskThread, JobException, TimeoutException
from golem.vm.memorychecker import MemoryChecker

if TYPE_CHECKING:
    from .manager import DockerManager  # noqa pylint:disable=unused-import


logger = logging.getLogger(__name__)


EXIT_CODE_MESSAGE = "Subtask computation failed with exit code {}"
EXIT_CODE_PROBABLE_CAUSES = {
    137: "probably killed by out-of-memory killer"
}


class ImageException(RuntimeError):
    pass

# TODO change the way OUTPUT_DIR and WORK_DIR are handled
# now there is duplication of declarations in DockerJob and here
# plus, there is GOLEM_BASE_PATH hardcoded here
class DockerTaskThread(TaskThread):

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    docker_manager: ClassVar[Optional['DockerManager']] = None

    def __init__(self, subtask_id,  # pylint: disable=too-many-arguments
                 docker_images, orig_script_dir, src_code, extra_data,
                 short_desc, res_path, tmp_path, timeout, check_mem=False):

        if not docker_images:
            raise AttributeError("docker images is None")
        super(DockerTaskThread, self).__init__(
            subtask_id, orig_script_dir, src_code, extra_data,
            short_desc, res_path, tmp_path, timeout)

        # Find available image
        self.image = None
        logger.debug("Checking docker images %s", docker_images)
        for img in docker_images:
            if img.is_available():
                self.image = img
                break

        self.job = None
        self.check_mem = check_mem

        self.work_dir_path: Path = Path(self.tmp_path) / DockerJob.WORK_DIR_E
        self.output_dir_path: Path = Path(self.tmp_path) / DockerJob.RESOURCES_DIR_E
        self.messages_input_path = Path(self.tmp_path) / DockerJob.WORK_DIR_E / DockerJob.MESSAGES_IN_DIR_E
        self.messages_output_path = Path(self.tmp_path) / DockerJob.WORK_DIR_E / DockerJob.MESSAGES_OUT_DIR_E

    def run(self) -> None:
        try:
            if not self.image:
                raise JobException("None of the Docker images are available")

            if self.use_timeout and self.task_timeout < 0:
                raise TimeoutException()

            estm_mem = self._run_docker_job()

        except (requests.exceptions.ReadTimeout, TimeoutException) as exc:
            if not self.use_timeout:
                self._fail(exc)
                return

            failure = TimeoutException("Task timed out after {:.1f}s"
                                       .format(self.time_to_compute))
            failure.with_traceback(exc.__traceback__)
            self._fail(failure)

        except Exception as exc:  # pylint: disable=broad-except
            self._fail(exc)

        else:
            self._task_computed(estm_mem)

        finally:
            self.job = None

    def _run_docker_job(self) -> Optional[int]:
        self.work_dir_path.mkdir(exist_ok=True)
        self.output_dir_path.mkdir(exist_ok=True)
        self.messages_input_path.mkdir(exist_ok=True)
        self.messages_output_path.mkdir(exist_ok=True)

        host_config = self.docker_manager.container_host_config \
            if self.docker_manager else None

        with DockerJob(self.image,
                       self.src_code,
                       self.extra_data,
                       self.res_path,
                       str(self.work_dir_path),
                       str(self.output_dir_path),
                       host_config=host_config) \
                as job, \
                MemoryChecker(self.check_mem) as mc:
            self.job = job
            self.job.start()
            exit_code = self.job.wait()

            self.job.dump_logs(str(self.output_dir_path / self.STDOUT_FILE),
                               str(self.output_dir_path / self.STDERR_FILE))

            estm_mem = mc.estm_mem

            if exit_code != 0:
                logger.warning(
                    'Task stderr:\n%s',
                    (self.output_dir_path / self.STDERR_FILE).read_text())
                raise JobException(self._exit_code_message(exit_code))

        return estm_mem

    def _task_computed(self, estm_mem: Optional[int]) -> None:
        out_files = [
            str(path) for path in self.output_dir_path.glob("**/*")
            if path.is_file()
        ]
        self.result = {
            "data": out_files,
            "result_type": ResultType.FILES,
        }
        if estm_mem is not None:
            self.result = (self.result, estm_mem)
        self._deferred.callback(self)

    def get_progress(self):
        # TODO: make the container update some status file? Issue #56
        return 0.0

    # TODO make the structure of msgs_decoded explicit somewhere
    # instead of "content": ..., "filename": ... hardcoded here
    def check_for_new_messages(self) -> List[Dict]:
        """ Check is the script produced any new messages
        :return: list containing list of messages, each of which is a dict
        """
        if not self.job:
            return [{}]
        msgs = self.job.read_work_files(dir=DockerJob.MESSAGES_OUT_DIR_E)
        msgs_decoded = []
        for filename, content in msgs.items():
            try:
                msgs_decoded.append(json.loads(content))
            except ValueError:
                msgs_decoded.append({})
                logger.warning("ValueError during decoding message %r", str(content))  # noqa

        # cleaning messages files, to not read multiple times the same content
        self.job.clean_work_files(dir=DockerJob.MESSAGES_OUT_DIR_E)

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
            msg_path = os.path.join(DockerJob.MESSAGES_IN_DIR_E, msg_filename)
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

    @staticmethod
    def _exit_code_message(exit_code):
        msg = EXIT_CODE_MESSAGE.format(exit_code)
        cause = EXIT_CODE_PROBABLE_CAUSES.get(exit_code)
        if not cause:
            return msg
        return "{} ({})".format(msg, cause)
