import cloudpickle
import json
import logging
import os
import posixpath
import threading
from typing import Dict, Optional, Iterable

import docker.errors

from golem.core.common import nt_path_to_posix_path, is_osx, is_windows
from golem.docker.image import DockerImage
from .client import local_client

__all__ = ['DockerJob']

logger = logging.getLogger(__name__)

"""
The logger used for logging std streams of the process running in container.
"""
container_logger = logging.getLogger(__name__ + ".container")


# pylint:disable=too-many-instance-attributes
class DockerJob:
    STATE_NEW = "new"
    STATE_CREATED = "created"  # container created by docker
    STATE_RUNNING = "running"  # docker container running
    STATE_EXITED = "exited"  # docker container finished running
    STATE_STOPPED = "stopped"
    STATE_KILLED = "killed"
    STATE_REMOVED = "removed"

    # This dir contains static task resources.
    # Mounted read-only in the container.
    RESOURCES_DIR = "/golem/resources"

    # This dir contains task script and params file.
    # Mounted read-write in the container.
    WORK_DIR = "/golem/work"

    # All files in this dir are treated as output files after the task finishes.
    # Mounted read-write in the container.
    OUTPUT_DIR = "/golem/output"

    # these keys/values pairs will be saved in "params" module - it is
    # dynamically created during docker setup and available for import
    # inside docker
    PATH_PARAMS = {
        "RESOURCES_DIR": RESOURCES_DIR,
        "WORK_DIR": WORK_DIR,
        "OUTPUT_DIR": OUTPUT_DIR
    }

    # Name of the parameters file, relative to WORK_DIR
    PARAMS_FILE = "params.json"

    # pylint:disable=too-many-arguments
    def __init__(self,
                 image: DockerImage,
                 script_filepath: str,
                 parameters: Dict,
                 resources_dir: str,
                 work_dir: str,
                 output_dir: str,
                 volumes: Optional[Iterable[str]] = None,
                 environment: Optional[dict] = None,
                 host_config: Optional[Dict] = None,
                 container_log_level: Optional[int] = None) -> None:
        """
        :param DockerImage image: Docker image to use
        :param str script_src: source of the task script file
        :param dict parameters: parameters for the task script
        :param str resources_dir: directory with task resources
        :param str work_dir: directory for temporary work files
        :param str output_dir: directory for output files
        """
        if not isinstance(image, DockerImage):
            raise TypeError('Incorrect image type: {}. '
                            'Should be: DockerImage'.format(type(image)))
        self.image = image
        self.script_filepath = script_filepath
        self.parameters = parameters if parameters else {}

        self.parameters.update(self.PATH_PARAMS)

        self.volumes = list(volumes) if volumes else [
            self.WORK_DIR,
            self.RESOURCES_DIR,
            self.OUTPUT_DIR
        ]
        self.environment = environment or {}
        self.host_config = host_config or {}

        self.resources_dir = resources_dir
        self.work_dir = work_dir
        self.output_dir = output_dir

        self.resources_dir_mod = None
        self.work_dir_mod = None
        self.output_dir_mod = None

        self.container = None
        self.container_id = None
        self.container_log = None
        self.state = self.STATE_NEW

        if container_log_level is None:
            container_log_level = container_logger.getEffectiveLevel()
        self.log_std_streams = 0 < container_log_level <= logging.DEBUG
        self.logging_thread = None
        self.stop_logging_thread = False

    def _prepare(self):
        self.work_dir_mod = self._host_dir_chmod(self.work_dir, "rw")
        self.resources_dir_mod = self._host_dir_chmod(self.resources_dir, "rw")
        self.output_dir_mod = self._host_dir_chmod(self.output_dir, "rw")

        # Save parameters in work_dir/PARAMS_FILE
        params_file_path = self._get_host_params_path()
        with open(params_file_path, "wb") as params_file:
            cloudpickle.dump(self.parameters, params_file)

        # Setup volumes for the container
        client = local_client()

        host_cfg = client.create_host_config(**self.host_config)

        self.container = client.create_container(
            image=self.image.name,
            volumes=self.volumes,
            host_config=host_cfg,
            command=[f'python3 "{self.script_filepath}"'],
            working_dir=self.WORK_DIR,
            environment=self.environment,
        )
        self.container_id = self.container["Id"]
        if self.container_id is None:
            raise KeyError("container does not have key: Id")

        logger.debug("Container %s prepared, image: %s, dirs: %s; %s; %s",
                     self.container_id, self.image.name, self.work_dir,
                     self.resources_dir, self.output_dir)

    def _cleanup(self):
        if self.container:
            client = local_client()
            self._host_dir_chmod(self.work_dir, self.work_dir_mod)
            self._host_dir_chmod(self.resources_dir, self.resources_dir_mod)
            self._host_dir_chmod(self.output_dir, self.output_dir_mod)
            try:
                client.remove_container(self.container_id, force=True)
                logger.debug("Container %s removed", self.container_id)
            except docker.errors.APIError:
                pass  # Already removed? Sometimes happens in CircleCI.
            self.container = None
            self.container_id = None
            self.state = self.STATE_REMOVED
        if self.logging_thread:
            self.stop_logging_thread = True
            self.logging_thread.join(1)
            if self.logging_thread.is_alive():
                logger.warning("Docker logging thread still running")
            else:
                logger.debug("Docker logging stopped")
            self.logging_thread = None

    def __enter__(self):
        self._prepare()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _get_host_params_path(self):
        return os.path.join(self.work_dir, self.PARAMS_FILE)

    @staticmethod
    def _host_dir_chmod(dst_dir, mod):
        if isinstance(mod, str):
            mod = 0o770 if mod == 'rw' else \
                0o550 if mod == 'ro' else 0
        prev_mod = None

        try:
            import stat
            prev_mod = stat.S_IMODE(os.stat(dst_dir).st_mode)
        except Exception as e:  # pylint:disable=broad-except
            logger.debug("Cannot get mode for %s, "
                         "reason: %s", dst_dir, e)

        if mod is not None:
            try:
                os.chmod(dst_dir, mod)
            except Exception as e:  # pylint:disable=broad-except
                logger.debug("Cannot chmod %s (%s): %s", dst_dir, mod, e)

        return prev_mod

    @staticmethod
    def get_absolute_resource_path(relative_path):
        return posixpath.join(DockerJob.RESOURCES_DIR,
                              nt_path_to_posix_path(relative_path))

    def _start_logging_thread(self, client):

        def log_stream(s):
            for chunk in s:
                container_logger.debug(chunk)
                if self.stop_logging_thread:
                    break

        stream = client.attach(self.container_id, stdout=True, stderr=True,
                               stream=True, logs=True)
        self.logging_thread = threading.Thread(
            target=log_stream, args=(stream,), name="ContainerLoggingThread")
        self.logging_thread.start()

    def start(self):
        if self.get_status() == self.STATE_CREATED:
            client = local_client()
            client.start(self.container_id)
            result = client.inspect_container(self.container_id)
            self.state = result["State"]["Status"]
            logger.debug("Container %s started", self.container_id)
            if self.log_std_streams:
                self._start_logging_thread(client)
            return result
        logger.debug("Container %s not started, status = %s",
                     self.container_id, self.get_status())
        return None

    def wait(self, timeout=None):
        """Block until the job completes, or timeout elapses.
        :param timeout: time to block
        :returns container exit code
        """
        if self.get_status() in [self.STATE_RUNNING, self.STATE_EXITED]:
            client = local_client()
            return client.wait(self.container_id, timeout).get('StatusCode')
        logger.debug("Cannot wait for container %s, status = %s",
                     self.container_id, self.get_status())
        return -1

    def kill(self):
        try:
            status = self.get_status()
        except Exception as exc:  # pylint:disable=broad-except
            status = None
            logger.error("Error retrieving status for container %s: %s",
                         self.container_id, exc)

        if status != self.STATE_RUNNING:
            return

        try:
            client = local_client()
            client.kill(self.container_id)
        except docker.errors.APIError as exc:
            logger.error("Couldn't kill container %s: %s",
                         self.container_id, exc)

    def dump_logs(self, stdout_file=None, stderr_file=None):
        if not self.container:
            return
        client = local_client()

        def dump_stream(stream, path):
            logger.debug('dump_stream(%r, %r)', stream, path)
            with open(path, "wb") as f:
                for line in stream:
                    f.write(line)
                f.flush()

        if stdout_file:
            stdout = client.logs(self.container_id,
                                 stream=True, stdout=True, stderr=False)
            dump_stream(stdout, stdout_file)
        if stderr_file:
            stderr = client.logs(self.container_id,
                                 stream=True, stdout=False, stderr=True)
            dump_stream(stderr, stderr_file)

    def get_status(self):
        if self.container:
            client = local_client()
            inspect = client.inspect_container(self.container_id)
            return inspect["State"]["Status"]
        return self.state

    @staticmethod
    def get_environment() -> dict:
        if is_windows():
            return {}
        if is_osx():
            return dict(OSX_USER=1)

        return dict(LOCAL_USER_ID=os.getuid())
