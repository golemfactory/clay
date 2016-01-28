from docker import Client
from docker import errors

from os import path
import os
import shutil
import tempfile


class DockerImage(object):

    def __init__(self, repository, id=None, tag=None):
        self.repository = repository
        self.id = id
        self.tag = tag if tag else "latest"
        self.name = "{}:{}".format(self.repository, self.tag)
        if not self._check():
            raise ValueError("Image name does not match image ID")

    def _check(self):
        client = Client()
        if self.id:
            info = client.inspect_image(self.id)
        else:
            info = client.inspect_image(self.name)
        # Check that name and ID agree
        assert info
        return self.name in info["RepoTags"] and (
            self.id is None or info["Id"] == self.id)

    @staticmethod
    def is_available(repository, id=None, tag=None):
        try:
            image = DockerImage(repository, id=id, tag=tag)
            return image._check()
        except errors.NotFound:
            return False
        except errors.APIError as e:
            if tag is not None:
                return False
            raise e
        except ValueError:
            return False


class DockerJob(object):

    STATE_CREATED = "created"
    STATE_RUNNING = "running"
    STATE_STOPPED = "stopped"
    STATE_KILLED = "killed"
    STATE_REMOVED = "removed"

    # name of the input dir, relative to the task dir)
    INPUT_DIR = "input"
    # name of the script file, relative to the task dir
    TASK_SCRIPT = path.join(INPUT_DIR, "job.py")
    # name of the resource dir, relative to the task dir
    RESOURCE_DIR = path.join(INPUT_DIR, "res")
    # name of the output dir, relative to the task dir
    OUTPUT_DIR = "output"

    def __init__(self, image, script_src, resource_dir, output_dir):
        """
        :param DockerImage image: Docker image to use
        :param str script_src: source of the script file
        :param str output_dir:
        :param str resource_dir:
        :return:
        """
        self.output_dir = output_dir

        # Create a temporary dir that will be mounted as a volume with
        # task script and resources
        self.task_dir = tempfile.mkdtemp(prefix="golem-")
        task_input_dir = self._get_input_dir()
        os.mkdir(task_input_dir, 0777)

        # Save the script in task_dir/TASK_SCRIPT
        task_script_path = self._get_script_path()
        with open(task_script_path, "w") as script_file:
            script_file.write(script_src)

        # Copy the resource files to task_dir/RESOURCE_DIR
        task_resource_dir = self._get_resource_dir()
        shutil.copytree(resource_dir, task_resource_dir)

        # Create a temporary dir that will be mounted as a volume into which
        # the output file is written
        task_output_dir = self._get_output_dir()
        os.mkdir(task_output_dir, 0777)

        # Setup volumes for the container
        client = Client()
        host_cfg = client.create_host_config(
            binds={
                task_input_dir: {
                    "bind": "/golem/input",
                    "mode": "ro"
                },
                task_output_dir: {
                    "bind": "/golem/output",
                    "mode": "rw"
                }
            }
        )

        self.container = client.create_container(
            image=image.name,
            volumes=["/golem/input", "/golem/output"],
            host_config = host_cfg,
            network_disabled=True)

        self.container_id = self.container["Id"]
        assert self.container_id
        self.state = self.STATE_CREATED

    def _get_input_dir(self):
        assert self.task_dir
        return path.join(self.task_dir, self.INPUT_DIR)

    def _get_resource_dir(self):
        assert self.task_dir
        return path.join(self.task_dir, self.RESOURCE_DIR)

    def _get_script_path(self):
        assert self.task_dir
        return path.join(self.task_dir, self.TASK_SCRIPT)

    def _get_output_dir(self):
        assert self.task_dir
        return path.join(self.task_dir, self.OUTPUT_DIR)

    def cleanup(self):
        """Removes the temporary directory task_dir"""
        if self.task_dir:
            shutil.rmtree(self.task_dir)

    def start(self):
        if self.state is self.STATE_CREATED:
            client = Client()
            client.start(self.container_id)
            result = client.inspect_container(self.container_id)
            self.state = self.STATE_RUNNING
            return result
        return None

    def get_status(self):
        client = Client()
        try:
            inspect = client.inspect_container(self.container_id)
            return inspect["State"]["Status"]
        except Exception:
            return self.STATE_REMOVED

    def is_running(self):
        return self.get_status() == "running"

    def remove(self, force=False):
        client = Client()
        if self.is_running():
            client.kill(self.container_id)
            self.state = self.STATE_KILLED
        client.remove_container(self.container_id, force=force)
        self.state = self.STATE_REMOVED
