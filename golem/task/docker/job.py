from golem.core.common import is_windows, nt_path_to_posix_path

from client import local_client

from os import path


class DockerJob(object):

    STATE_NEW = "new"
    STATE_CREATED = "created"  # container created by docker
    STATE_RUNNING = "running"  # docker container running
    STATE_EXITED = "exited"    # docker container finished running
    STATE_STOPPED = "stopped"
    STATE_KILLED = "killed"
    STATE_REMOVED = "removed"

    # name of the script file, relative to the task dir
    TASK_SCRIPT = "job.py"
    # name of the parameters file, relative to the task dir
    PARAMS_FILE = "params.py"

    RESOURCES_DIR = "/golem/resources"
    OUTPUT_DIR = "/golem/output"

    def __init__(self, image, script_src, parameters,
                 work_dir, resource_dir, output_dir):
        """
        :param DockerImage image: Docker image to use
        :param str script_src: source of the script file
        :param str output_dir:
        :param str resource_dir:
        """
        self.image = image
        self.script_src = script_src
        self.parameters = parameters if parameters else {}
        self.work_dir = work_dir
        self.resource_dir = resource_dir
        self.output_dir = output_dir

        self.task_dir = path.join(self.resource_dir, self.work_dir)
        self.container = None
        self.container_id = None
        self.container_log = None
        self.state = self.STATE_NEW

    def _prepare(self):
        # Save parameters in task_dir/PARAMS_FILE
        params_file_path = self._get_params_path()
        with open(params_file_path, "w") as params_file:
            for key, value in self.parameters.iteritems():
                line = "{} = {}\n".format(key, repr(value))
                params_file.write(bytearray(line, encoding='utf-8'))
        self.script_src = "from params import *\n\n" + self.script_src

        # Save the script in task_dir/TASK_SCRIPT
        task_script_path = self._get_script_path()
        with open(task_script_path, "w") as script_file:
            script_file.write(bytearray(self.script_src, "utf-8"))

        # Setup volumes for the container
        client = local_client()

        resource_dir_key = self.resource_dir if not is_windows() \
            else nt_path_to_posix_path(self.resource_dir)
        output_dir_key = self.output_dir if not is_windows()\
            else nt_path_to_posix_path(self.output_dir)

        host_cfg = client.create_host_config(
            binds={
                resource_dir_key: {
                    "bind": self.RESOURCES_DIR,
                    "mode": "ro"
                },
                output_dir_key: {
                    "bind": self.OUTPUT_DIR,
                    "mode": "rw"
                }
            }
        )

        # The location of the task script when mounted in the container
        container_script_path = "/".join(
            [self.RESOURCES_DIR, self.work_dir, self.TASK_SCRIPT])
        self.container = client.create_container(
            image=self.image.name,
            volumes=[self.RESOURCES_DIR, self.OUTPUT_DIR],
            host_config=host_cfg,
            network_disabled=True,
            command=[container_script_path],
            working_dir=path.dirname(container_script_path)
        )

        self.container_id = self.container["Id"]
        assert self.container_id

    def _cleanup(self):
        if self.container:
            client = local_client()
            client.remove_container(self.container_id, force=True)
            self.container = None
            self.container_id = None
            self.state = self.STATE_REMOVED

    def __enter__(self):
        self._prepare()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._cleanup()

    def _get_script_path(self):
        return path.join(self.task_dir, self.TASK_SCRIPT)

    def _get_params_path(self):
        return path.join(self.task_dir, self.PARAMS_FILE)

    def start(self):
        if self.get_status() == self.STATE_CREATED:
            client = local_client()
            client.start(self.container_id)
            result = client.inspect_container(self.container_id)
            self.state = result["State"]["Status"]
            return result
        return None

    def wait(self, timeout=None):
        """Block until the job completes, or timeout elapses.
        :param timeout: time to block
        :returns container exit code
        """
        if self.get_status() in [self.STATE_RUNNING, self.STATE_EXITED]:
            client = local_client()
            return client.wait(self.container_id, timeout)
        return -1

    def dump_logs(self, stdout_file=None, stderr_file=None):
        if not self.container:
            return
        client = local_client()

        def dump_stream(stream, path):
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
