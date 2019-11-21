# coding: utf-8
import logging.config
import json
import os
import shutil
import tempfile
import time
import uuid
from os import path
import unittest.mock as mock

import docker.errors
import requests

from golem.core.common import config_logging
from golem.core.common import is_windows, nt_path_to_posix_path
from golem.core.simpleenv import get_local_datadir
from golem.docker.client import local_client
from golem.docker.image import DockerImage
from golem.docker.job import DockerJob, container_logger
from golem.tools.ci import ci_skip
from tests.golem.docker.test_docker_image import DockerTestCase

config_logging('docker_test')


class TestDockerJob(DockerTestCase):
    """Common superclass for Docker job tests"""

    def _get_test_repository(self):
        """Abstract method, should be overriden by subclasses"""
        pass

    # pylint:disable=no-self-use
    def _get_test_tag(self):
        return "latest"

    TEST_SCRIPT = "print 'Adventure Time!'\n"

    def setUp(self):
        main_dir = get_local_datadir('tests-' + str(uuid.uuid4()))
        if not os.path.exists(main_dir):
            os.makedirs(main_dir)

        self.test_dir = tempfile.mkdtemp(dir=main_dir)
        self.work_dir = tempfile.mkdtemp(prefix="golem-", dir=self.test_dir)
        self.resources_dir = tempfile.mkdtemp(
            prefix="golem-", dir=self.test_dir)
        self.output_dir = tempfile.mkdtemp(prefix="golem-", dir=self.test_dir)
        self.stats_dir = tempfile.mkdtemp(prefix="golem-", dir=self.test_dir)

        if not is_windows():
            os.chmod(self.test_dir, 0o770)

        self.image = DockerImage(self._get_test_repository(),
                                 tag=self._get_test_tag())
        self.test_job = None

    def testDockerJobInit(self):
        with self.assertRaises(TypeError):
            DockerJob(None, "scr", [], '/var/lib/resources/',
                      '/var/lib/work', '/var/lib/out')
        job = DockerJob(self.image, self.TEST_SCRIPT, None, self.resources_dir,
                        self.work_dir, self.output_dir, self.stats_dir)
        self.assertEqual(job.image, self.image)

        parameters = {'OUTPUT_DIR': '/golem/output',
                      'RESOURCES_DIR': '/golem/resources',
                      'WORK_DIR': '/golem/work', 'STATS_DIR': '/golem/stats'}
        self.assertEqual(job.parameters, parameters)
        self.assertEqual(job.host_config, {})
        self.assertEqual(job.resources_dir, self.resources_dir)
        self.assertEqual(job.work_dir, self.work_dir)
        self.assertEqual(job.output_dir, self.output_dir)
        self.assertIsNone(job.resources_dir_mod)
        self.assertIsNone(job.work_dir_mod)
        self.assertIsNone(job.output_dir_mod)
        self.assertIsNone(job.container)
        self.assertIsNone(job.container_id)
        self.assertIsNone(job.container_log)
        self.assertEqual(job.state, 'new')
        self.assertIsNone(job.logging_thread)

    def tearDown(self):
        if self.test_job and self.test_job.container:
            client = local_client()
            try:
                client.remove_container(self.test_job.container_id,
                                        force=True)
            except docker.errors.APIError:
                pass  # Already removed?
        self.test_job = None
        if self.test_dir:
            shutil.rmtree(self.test_dir)

    def _create_test_job(self, script=TEST_SCRIPT, params=None, cpu_limit=None):
        self.test_job = DockerJob(
            image=self.image,
            entrypoint=f'python3 {script}',
            parameters=params,
            resources_dir=self.resources_dir,
            work_dir=self.work_dir,
            output_dir=self.output_dir,
            stats_dir=self.stats_dir,
            host_config={
                'binds': {
                    self.work_dir: {
                        "bind": DockerJob.WORK_DIR,
                        "mode": "rw"
                    },
                    self.resources_dir: {
                        "bind": DockerJob.RESOURCES_DIR,
                        "mode": "rw"
                    },
                    self.output_dir: {
                        "bind": DockerJob.OUTPUT_DIR,
                        "mode": "rw"
                    },
                    self.stats_dir: {
                        "bind": DockerJob.STATS_DIR,
                        "mode": "rw"
                    }
                }
            },
            cpu_limit=cpu_limit)
        return self.test_job


@ci_skip
class TestBaseDockerJob(TestDockerJob):
    """Tests Docker job using the base image golem/base"""

    def _get_test_repository(self):
        return "golemfactory/base"

    def _get_test_tag(self):
        return "1.4"

    def test_create(self):
        job = self._create_test_job()

        self.assertIsNone(job.container)
        self.assertEqual(job.state, DockerJob.STATE_NEW)
        self.assertIsNotNone(job.work_dir)
        self.assertIsNotNone(job.resources_dir)
        self.assertIsNotNone(job.output_dir)
        self.assertIsNotNone(job.stats_dir)
        self.assertTrue(job._get_host_params_path().startswith(job.work_dir))

    def _load_dict(self, path):
        with open(path, 'r') as f:
            return json.load(f)

    def _test_params_saved(self, task_params):
        with self._create_test_job(params=task_params) as job:
            params_path = job._get_host_params_path()
            self.assertTrue(path.isfile(params_path))
            params = self._load_dict(params_path)
            self.assertEqual(params, task_params)

    def test_params_saved(self):
        self._test_params_saved({"name": "Jake", "age": 30})

    def test_params_saved_nonascii(self):
        # key has to be a valid Python ident, so we put nonascii chars
        # only in param values:
        self._test_params_saved({"length": "pięćdziesiąt łokci"})

    def test_container_created(self):
        with self._create_test_job() as job:
            self.assertIsNotNone(job.container_id)
            client = local_client()
            info = client.inspect_container(job.container_id)
            self.assertEqual(info["Id"], job.container_id)
            self.assertEqual(info["State"]["Status"], "created")
            self.assertFalse(info["State"]["Running"])

            image_id = client.inspect_image(self.image.name)["Id"]
            self.assertEqual(info["Image"], image_id)

    def test_mounts(self):
        with self._create_test_job() as job:
            client = local_client()
            info = client.inspect_container(job.container_id)

            work_mount = None
            resources_mount = None
            output_mount = None
            stats_mount = None
            for mount in info["Mounts"]:
                if mount["Destination"] == DockerJob.WORK_DIR:
                    work_mount = mount
                elif mount["Destination"] == DockerJob.RESOURCES_DIR:
                    resources_mount = mount
                elif mount["Destination"] == DockerJob.OUTPUT_DIR:
                    output_mount = mount
                elif mount["Destination"] == DockerJob.STATS_DIR:
                    stats_mount = mount

            work_dir = self.work_dir if not is_windows() \
                else nt_path_to_posix_path(self.work_dir)
            resource_dir = self.resources_dir if not is_windows() \
                else nt_path_to_posix_path(self.resources_dir)
            output_dir = self.output_dir if not is_windows()\
                else nt_path_to_posix_path(self.output_dir)
            stats_dir = self.stats_dir if not is_windows() \
                else nt_path_to_posix_path(self.stats_dir)

            self.assertIsNotNone(work_mount)
            self.assertEqual(work_mount["Source"], work_dir)
            self.assertTrue(work_mount["RW"])
            self.assertIsNotNone(resources_mount)
            self.assertEqual(resources_mount["Source"], resource_dir)
            self.assertTrue(resources_mount["RW"])
            self.assertIsNotNone(output_mount)
            self.assertEqual(output_mount["Source"], output_dir)
            self.assertTrue(output_mount["RW"])
            self.assertTrue(stats_mount["Source"], stats_dir)
            self.assertTrue(stats_mount["RW"])

    def test_cleanup(self):
        with self._create_test_job() as job:
            container_id = job.container_id
            self.assertIsNotNone(container_id)

        self.assertIsNone(job.container_id)
        with self.assertRaises(docker.errors.NotFound):
            client = local_client()
            client.inspect_container(container_id)

    def test_status(self):
        job = self._create_test_job()
        self.assertEqual(job.get_status(), DockerJob.STATE_NEW)
        job._prepare()
        self.assertEqual(job.get_status(), DockerJob.STATE_CREATED)
        job.start()
        self.assertTrue(job.get_status() in
                        [DockerJob.STATE_EXITED, DockerJob.STATE_RUNNING])
        job._cleanup()
        self.assertEqual(job.state, DockerJob.STATE_REMOVED)

        with self._create_test_job() as job2:
            self.assertEqual(job2.get_status(), DockerJob.STATE_CREATED)
        self.assertEqual(job2.get_status(), DockerJob.STATE_REMOVED)

    def test_start(self):
        with self._create_test_job() as job:
            job.start()
            client = local_client()
            info = client.inspect_container(job.container_id)
            self.assertIn("Path", info)
            self.assertEqual(info["Path"], "/usr/local/bin/entrypoint.sh")
            self.assertIn("Args", info)

    def test_logs_stdout(self):
        text = "Adventure Time!"
        src = "print('{}')\n".format(text)
        with open(path.join(self.resources_dir, "custom.py"), "w") as f:
            f.write(src)
        with self._create_test_job(script='/golem/resources/custom.py') as job:
            job.start()
            out_file = path.join(self.output_dir, "stdout.log")
            err_file = path.join(self.output_dir, "stderr.log")
            job.dump_logs(out_file, err_file)
        out_files = os.listdir(self.output_dir)
        self.assertEqual(set(out_files), {"stdout.log", "stderr.log"})
        with open(out_file, "r") as out:
            line = out.readline().strip()
        self.assertEqual(line, text)

    def test_logs_stderr(self):
        with self._create_test_job(script="/non/existing") as job:
            job.start()
            err_file = path.join(self.output_dir, "stderr.log")
            job.dump_logs(stderr_file=err_file)
        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ["stderr.log"])
        with open(err_file, "r") as out:
            line = out.readline().strip()
        print(line)
        self.assertTrue(line.find("python3: can't open file") != -1)

    def test_stats_entrypoint_no_limit(self):
        with self._create_test_job(script='/non/existent') as job:
            stats_entrypoint = job._build_stats_entrypoint()
            self.assertEqual(
                stats_entrypoint,
                'docker-cgroups-stats '
                '-o /golem/stats/stats.json python3 /non/existent'
            )

    def test_stats_entrypoint_with_limit(self):
        with self._create_test_job(script='/non/existent', cpu_limit=1) as job:
            stats_entrypoint = job._build_stats_entrypoint()
            self.assertEqual(
                stats_entrypoint,
                'docker-cgroups-stats '
                '-l 1 -o /golem/stats/stats.json python3 /non/existent'
            )

    def test_wait_timeout(self):
        src = "import time\ntime.sleep(10)\n"
        with open(path.join(self.resources_dir, "custom.py"), "w") as f:
            f.write(src)
        with self.assertRaises(requests.exceptions.ConnectionError):
            with self._create_test_job(script='/golem/resources/custom.py') \
                    as job:
                job.start()
                self.assertEqual(job.get_status(), DockerJob.STATE_RUNNING)
                job.wait(1)

    def test_start_cleanup(self):
        # Ensure logging thread is created
        prev_level = container_logger.getEffectiveLevel()
        container_logger.setLevel(logging.DEBUG)
        with self._create_test_job() as job:
            job.start()
            logging_thread = job.logging_thread
            self.assertIsNotNone(logging_thread)
            self.assertTrue(logging_thread.is_alive())
            job.wait()
        if logging_thread.is_alive():
            time.sleep(1)
        self.assertIsNone(job.logging_thread)
        self.assertFalse(logging_thread.is_alive())
        container_logger.setLevel(prev_level)

    def test_logger_thread(self):
        # Ensure logging thread is created
        prev_level = container_logger.getEffectiveLevel()

        container_logger.setLevel(logging.DEBUG)
        with self._create_test_job() as job:
            job.start()
            logging_thread = job.logging_thread
            self.assertIsNotNone(logging_thread)
            self.assertTrue(logging_thread.is_alive())
            job.wait()
        if logging_thread.is_alive():
            time.sleep(1)
        self.assertIsNone(job.logging_thread)
        self.assertFalse(logging_thread.is_alive())

        # Ensure the thread is not created if level > DEBUG
        container_logger.setLevel(logging.INFO)
        with self._create_test_job() as job:
            job.start()
            self.assertIsNone(job.logging_thread)
            job.wait()

        container_logger.setLevel(prev_level)

    def test_working_dir_set(self):
        script = "import os\nprint(os.getcwd())\n"
        with open(path.join(self.resources_dir, "custom.py"), "w") as f:
            f.write(script)
        with self._create_test_job(script='/golem/resources/custom.py') as job:
            job.start()
            job.wait()
            out_file = path.join(self.output_dir, "stdout.log")
            job.dump_logs(stdout_file=out_file)
        with open(out_file, "rb") as out:
            line = out.readline().decode('utf-8').strip()
        self.assertEqual(line, DockerJob.WORK_DIR)

    def test_copy_job(self):
        """Creates a sample resource file and a task script that copies
        the resource file to the output file. Also tests if the work_dir
        is set to the script dir (by using paths relative to the script dir).
        """
        copy_script = """
with open("../resources/in.txt", "r") as f:
    text = f.read()

with open("../output/out.txt", "w") as f:
    f.write(text)
"""
        sample_text = "Adventure Time!\n"

        with open(path.join(self.resources_dir, "in.txt"), "w") as f:
            f.write(sample_text)
        with open(path.join(self.resources_dir, "copy.py"), "w") as f:
            f.write(copy_script)

        with self._create_test_job(script='/golem/resources/copy.py') as job:
            job.start()
            job.wait()

        outfile = path.join(self.output_dir, "out.txt")
        self.assertTrue(path.isfile(outfile))
        with open(outfile, "r") as f:
            text = f.read()
        self.assertEqual(text, sample_text)

    @mock.patch('golem.docker.job.local_client')
    def test_kill(self, local_client):

        client = mock.Mock()
        local_client.return_value = client

        def raise_exception(*_):
            raise Exception("Test exception")

        with mock.patch('golem.docker.job.DockerJob.get_status',
                        side_effect=raise_exception):
            job = self._create_test_job("test_script")
            job.kill()
            assert not local_client.called
            assert not client.kill.called

        with mock.patch('golem.docker.job.DockerJob.get_status',
                        return_value=DockerJob.STATE_KILLED):
            job = self._create_test_job("test_script")
            job.kill()
            assert not local_client.called
            assert not client.kill.called

        with mock.patch('golem.docker.job.DockerJob.get_status',
                        return_value=DockerJob.STATE_RUNNING):
            job = self._create_test_job("test_script")
            job.kill()
            assert local_client.called
            assert client.kill.called
