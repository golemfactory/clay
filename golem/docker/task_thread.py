import json
import logging
from pathlib import Path
from typing import ClassVar, Optional, TYPE_CHECKING, Tuple, Dict, Union, \
    List

import requests

from golem.docker.image import DockerImage
from golem.docker.job import DockerJob
from golem.environments.environmentsmanager import EnvironmentsManager
from golem.envs.docker import DockerBind
from golem.task.taskthread import TaskThread, JobException, TimeoutException, \
    BudgetExceededException
from golem.vm.memorychecker import MemoryChecker

if TYPE_CHECKING:
    from .manager import DockerManager  # noqa pylint:disable=unused-import


logger = logging.getLogger(__name__)


EXIT_CODE_BUDGET_EXCEEDED = 111
EXIT_CODE_MESSAGE = "Subtask computation failed with exit code {}"
EXIT_CODE_PROBABLE_CAUSES = {
    EXIT_CODE_BUDGET_EXCEEDED: "CPU budget exceeded",
    137: "probably killed by out-of-memory killer"
}


class ImageException(RuntimeError):
    pass


class DockerDirMapping:

    def __init__(self,   # pylint: disable=too-many-arguments
                 resources: Path, temporary: Path,
                 work: Path, output: Path, logs: Path, stats: Path) -> None:

        self.resources: Path = resources
        self.temporary: Path = temporary
        self.work: Path = work
        self.output: Path = output
        self.stats: Path = stats
        self.logs: Path = logs

    @classmethod
    def generate(cls, resources: Path, temporary: Path) -> 'DockerDirMapping':
        work = temporary / "work"
        output = temporary / "output"
        stats = temporary / "stats"
        logs = output

        return cls(resources, temporary, work, output, logs, stats)

    def mkdirs(self, exist_ok: bool = True) -> None:
        self.resources.mkdir(parents=True, exist_ok=exist_ok)
        self.temporary.mkdir(parents=True, exist_ok=exist_ok)
        self.work.mkdir(exist_ok=exist_ok)
        self.output.mkdir(exist_ok=exist_ok)
        self.stats.mkdir(exist_ok=exist_ok)
        self.logs.mkdir(exist_ok=exist_ok)


class DockerTaskThread(TaskThread):

    # These files will be placed in the output dir (self.tmp_path)
    # and will contain dumps of the task script's stdout and stderr.
    STDOUT_FILE = "stdout.log"
    STDERR_FILE = "stderr.log"

    docker_manager: ClassVar[Optional['DockerManager']] = None

    def __init__(self,  # pylint: disable=too-many-arguments
                 docker_images: List[Union[DockerImage, Dict, Tuple]],
                 extra_data: Dict,
                 dir_mapping: DockerDirMapping,
                 timeout: int,
                 cpu_limit: Optional[int] = None,
                 check_mem: bool = False) -> None:

        if not docker_images:
            raise AttributeError("docker images is None")
        super().__init__(
            extra_data=extra_data,
            res_path=str(dir_mapping.resources),
            tmp_path=str(dir_mapping.temporary),
            timeout=timeout
        )

        # Find available image
        self.image = None
        logger.debug("Checking docker images %s", docker_images)
        for img in docker_images:
            img = DockerImage.build(img)
            if img.is_available():
                self.image = img
                break

        self.job: Optional[DockerJob] = None
        self.check_mem = check_mem
        self.dir_mapping = dir_mapping
        self.cpu_limit = cpu_limit

    # pylint:disable=too-many-arguments
    @staticmethod
    def specify_dir_mapping(
            resources: str,
            temporary: str,
            work: str,
            output: str,
            logs: str,
            stats: str) -> DockerDirMapping:
        return DockerDirMapping(Path(resources), Path(temporary), Path(work),
                                Path(output), Path(logs), Path(stats))

    @staticmethod
    def generate_dir_mapping(resources: str, temporary: str) \
            -> DockerDirMapping:
        return DockerDirMapping.generate(Path(resources), Path(temporary))

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

    def _get_default_binds(self) -> List[DockerBind]:
        return [
            DockerBind(self.dir_mapping.work, DockerJob.WORK_DIR),
            DockerBind(self.dir_mapping.resources, DockerJob.RESOURCES_DIR),
            DockerBind(self.dir_mapping.output, DockerJob.OUTPUT_DIR),
            DockerBind(self.dir_mapping.stats, DockerJob.STATS_DIR)
        ]

    def _run_docker_job(self) -> Optional[int]:
        self.dir_mapping.mkdirs()

        binds = self._get_default_binds()
        volumes = list(bind.target for bind in binds)
        environment = dict(
            WORK_DIR=DockerJob.WORK_DIR,
            RESOURCES_DIR=DockerJob.RESOURCES_DIR,
            OUTPUT_DIR=DockerJob.OUTPUT_DIR,
            STATS_DIR=DockerJob.STATS_DIR,
        )

        assert self.image is not None
        docker_env = EnvironmentsManager().get_environment_by_image(self.image)

        if docker_env:
            env_config = docker_env.get_container_config()

            environment.update(env_config['environment'])
            binds += env_config['binds']
            volumes += env_config['volumes']
            devices = env_config['devices']
            runtime = env_config['runtime']
        else:
            logger.debug('No Docker environment found for image %r', self.image)

            devices = None
            runtime = None

        assert self.docker_manager is not None, "Docker Manager undefined"
        # PyLint still thinks docker_manager is of type DockerConfigManager
        # pylint: disable=no-member
        host_config = self.docker_manager.get_host_config_for_task(binds)
        host_config['devices'] = devices
        host_config['runtime'] = runtime

        params = dict(
            image=self.image,
            entrypoint=self.extra_data['entrypoint'],
            parameters=self.extra_data,
            resources_dir=str(self.dir_mapping.resources),
            work_dir=str(self.dir_mapping.work),
            output_dir=str(self.dir_mapping.output),
            stats_dir=str(self.dir_mapping.stats),
            volumes=volumes,
            environment=environment,
            host_config=host_config,
            cpu_limit=self.cpu_limit
        )

        with DockerJob(**params) as job, MemoryChecker(self.check_mem) as mc:
            self.job = job
            job.start()

            exit_code = job.wait()
            estm_mem = mc.estm_mem

            job.dump_logs(str(self.dir_mapping.logs / self.STDOUT_FILE),
                          str(self.dir_mapping.logs / self.STDERR_FILE))

            if exit_code != 0:
                std_err = (self.dir_mapping.logs / self.STDERR_FILE).read_text()
                with (self.dir_mapping.logs / self.STDOUT_FILE).open() as f:
                    lines = f.readlines()
                    std_out = "".join(lines[-21:])
                logger.warning(f'Task error - exit_code={exit_code}\n'
                               f'stderr:\n{std_err}\n'
                               f'tail of stdout:\n{std_out}\n')

                if exit_code == EXIT_CODE_BUDGET_EXCEEDED:
                    raise BudgetExceededException(
                        self._exit_code_message(exit_code))
                else:
                    raise JobException(self._exit_code_message(exit_code))

        return estm_mem

    def _task_computed(self, estm_mem: Optional[int]) -> None:
        out_files = [str(path) for path in self.dir_mapping.output.glob("*")]

        self.result = {
            "data": out_files,
        }

        self.stats = self.get_stats()

        if estm_mem is not None:
            self.result = (self.result, estm_mem)
        self._deferred.callback(self)

    def get_progress(self):
        # TODO: make the container update some status file? Issue #56
        return 0.0

    def get_stats(self) -> Dict:
        stats_file: Path = self.dir_mapping.stats / DockerJob.STATS_FILE

        if not stats_file.exists():
            return {}

        try:
            with stats_file.open() as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.warning(
                f'Failed to parse stats file: {stats_file}.', exc_info=e)
            return {}

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
