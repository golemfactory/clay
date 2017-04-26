import atexit
import logging
import os
import posixpath
import threading
from os import path

import docker.errors

from golem.core.common import is_windows, nt_path_to_posix_path, is_osx
from client import local_client

__all__ = ['DockerJob']

logger = logging.getLogger(__name__)

"""
The logger used for logging std streams of the process running in container.
"""
container_logger = logging.getLogger(__name__ + ".container")


class DockerJob(object):

    STATE_NEW = "new"
    STATE_CREATED = "created"  # container created by docker
    STATE_RUNNING = "running"  # docker container running
    STATE_EXITED = "exited"    # docker container finished running
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

    # Name of the script file, relative to WORK_DIR
    TASK_SCRIPT = "job.py"

    # Name of the parameters file, relative to WORK_DIR
    PARAMS_FILE = "params.py"

    running_jobs = []

    def __init__(self, image, script_src, parameters,
                 resources_dir, work_dir, output_dir,
                 host_config=None, container_log_level=None):
        """
        :param DockerImage image: Docker image to use
        :param str script_src: source of the task script file
        :param dict parameters: parameters for the task script
        :param str resources_dir: directory with task resources
        :param str work_dir: directory for temporary work files
        :param str output_dir: directory for output files
        """
        from golem.docker.image import DockerImage
        if not isinstance(image, DockerImage):
            raise TypeError('Incorrect image type: {}. Should be: DockerImage'.format(type(image)))
        self.image = image
        self.script_src = script_src
        self.parameters = parameters if parameters else {}
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

    def _prepare(self):
        self.work_dir_mod = self._host_dir_chmod(self.work_dir, "rw")
        self.resources_dir_mod = self._host_dir_chmod(self.resources_dir, "rw")
        self.output_dir_mod = self._host_dir_chmod(self.output_dir, "rw")

        # Save parameters in work_dir/PARAMS_FILE
        params_file_path = self._get_host_params_path()
        with open(params_file_path, "w") as params_file:
            for key, value in self.parameters.iteritems():
                line = "{} = {}\n".format(key, repr(value))
                params_file.write(bytearray(line, encoding='utf-8'))

        # Save the script in work_dir/TASK_SCRIPT
        task_script_path = self._get_host_script_path()
        with open(task_script_path, "w") as script_file:
            script_file.write(bytearray(self.script_src, "utf-8"))

        # Setup volumes for the container
        client = local_client()

        # Docker config requires binds to be specified using posix paths,
        # even on Windows. Hence this function:
        def posix_path(path):
            if is_windows():
                return nt_path_to_posix_path(path)
            return path

        container_config = dict(self.host_config)
        cpuset = container_config.pop('cpuset', None)

        if is_windows():
            environment = None
        elif is_osx():
            environment = dict(OSX_USER=1)
        else:
            environment = dict(LOCAL_USER_ID=os.getuid())

        host_cfg = client.create_host_config(
            binds={
                posix_path(self.work_dir): {
                    "bind": self.WORK_DIR,
                    "mode": "rw"
                },
                posix_path(self.resources_dir): {
                    "bind": self.RESOURCES_DIR,
                    "mode": "ro"
                },
                posix_path(self.output_dir): {
                    "bind": self.OUTPUT_DIR,
                    "mode": "rw"
                }
            },
            **container_config
        )

        # The location of the task script when mounted in the container
        container_script_path = self._get_container_script_path()
        self.container = client.create_container(
            image=self.image.name,
            volumes=[self.WORK_DIR, self.RESOURCES_DIR, self.OUTPUT_DIR],
            host_config=host_cfg,
            command=[container_script_path],
            working_dir=self.WORK_DIR,
            cpuset=cpuset,
            environment=environment
        )
        self.container_id = self.container["Id"]
        if self.container_id is None:
            raise KeyError("container does not have key: Id")

        self.running_jobs.append(self)
        logger.debug("Container {} prepared, image: {}, dirs: {}; {}; {}"
                     .format(self.container_id, self.image.name,
                             self.work_dir, self.resources_dir, self.output_dir)
                     )

    def _cleanup(self):
        if self.container:
            self.running_jobs.remove(self)
            client = local_client()
            self._host_dir_chmod(self.work_dir, self.work_dir_mod)
            self._host_dir_chmod(self.resources_dir, self.resources_dir_mod)
            self._host_dir_chmod(self.output_dir, self.output_dir_mod)
            try:
                client.remove_container(self.container_id, force=True)
                logger.debug("Container {} removed".format(self.container_id))
            except docker.errors.APIError:
                pass  # Already removed? Sometimes happens in CircleCI.
            self.container = None
            self.container_id = None
            self.state = self.STATE_REMOVED
        if self.logging_thread:
            self.logging_thread.join()
            self.logging_thread = None

    def __enter__(self):
        self._prepare()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _get_host_script_path(self):
        return path.join(self.work_dir, self.TASK_SCRIPT)

    def _get_host_params_path(self):
        return path.join(self.work_dir, self.PARAMS_FILE)

    @staticmethod
    def _host_dir_chmod(dst_dir, mod):
        if isinstance(mod, basestring):
            mod = 0770 if mod == 'rw' else \
                  0550 if mod == 'ro' else 0
        prev_mod = None

        try:
            import stat
            prev_mod = stat.S_IMODE(os.stat(dst_dir).st_mode)
        except Exception as e:
            logger.debug("Cannot get mode for {}, reason: {}".format(dst_dir, e))

        if mod is not None:
            try:
                os.chmod(dst_dir, mod)
            except Exception as e:
                logger.debug("Cannot chmod {} ({}): {}".format(dst_dir, mod, e))

        return prev_mod

    @staticmethod
    def _get_container_script_path():
        return posixpath.join(DockerJob.WORK_DIR, DockerJob.TASK_SCRIPT)

    @staticmethod
    def get_absolute_resource_path(relative_path):
        return posixpath.join(DockerJob.RESOURCES_DIR,
                              nt_path_to_posix_path(relative_path))

    def _start_logging_thread(self, client):

        def log_stream(s):
            for chunk in s:
                container_logger.debug(chunk)

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
            logger.debug("Container {} started".format(self.container_id))
            if self.log_std_streams:
                self._start_logging_thread(client)
            return result
        logger.debug("Container {} not started, status = {}"
                     .format(self.container_id, self.get_status()))
        return None

    def wait(self, timeout=None):
        """Block until the job completes, or timeout elapses.
        :param timeout: time to block
        :returns container exit code
        """
        if self.get_status() in [self.STATE_RUNNING, self.STATE_EXITED]:
            client = local_client()
            return client.wait(self.container_id, timeout)
        logger.debug("Cannot wait for container {}, status = {}"
                     .format(self.container_id, self.get_status()))
        return -1

    def kill(self):
        try:
            status = self.get_status()
        except Exception as exc:
            status = None
            logger.error("Error retrieving status for container {}: {}"
                         .format(self.container_id, exc))

        if status != self.STATE_RUNNING:
            return

        try:
            client = local_client()
            client.kill(self.container_id)
        except Exception as exc:
            logger.error("Couldn't kill container {}: {}"
                         .format(self.container_id, exc))

    def dump_logs(self, stdout_file=None, stderr_file=None):
        if not self.container:
            return
        client = local_client()

        def dump_stream(stream, path):
            logger.debug('dump_stream(%r, %r)', stream, path)
            with open(path, "w") as f:
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
    @atexit.register
    def kill_jobs():
        for job in DockerJob.running_jobs:
            logger.info("Killing job {}".format(job.container_id))
            job.kill()
