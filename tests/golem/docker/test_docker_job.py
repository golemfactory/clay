# coding: utf-8
import logging.config
import os
import requests
import shutil
import tempfile
from os import path

from docker import errors

from golem.core.common import is_windows, nt_path_to_posix_path
from golem.task.docker.image import DockerImage
from golem.task.docker.job import DockerJob, container_logger

from test_docker_image import DockerTestCase

logging.config.fileConfig(path.join(path.dirname(__file__), "logging.ini"),
                          disable_existing_loggers=False)


class TestDockerJob(DockerTestCase):
    """Common superclass for Docker job tests"""

    def _get_test_repository(self):
        """Abstract method, should be overriden by subclasses"""
        pass

    TEST_SCRIPT = "print 'Adventure Time!'\n"

    def setUp(self):
        tmpdir = path.expandvars("$TMP")
        if tmpdir != "$TMP":
            # $TMP should be set on Windows, e.g. to
            # "C:\Users\<user>\AppData\Local\Temp".
            # Without 'dir = tmpdir' we would get a dir inside $TMP,
            # but with a path converted to lowercase, e.g.
            # "c:\users\<user>\appdata\local\temp\golem-<random-string>".
            # This wouldn't work with Docker.
            self.work_dir = tempfile.mkdtemp(prefix="golem-", dir=tmpdir)
            self.resources_dir = tempfile.mkdtemp(prefix="golem-", dir=tmpdir)
            self.output_dir = tempfile.mkdtemp(prefix="golem-", dir=tmpdir)
        else:
            self.work_dir = tempfile.mkdtemp(prefix="golem-")
            self.resources_dir = tempfile.mkdtemp(prefix="golem-")
            self.output_dir = tempfile.mkdtemp(prefix="golem-")

        self.image = DockerImage(self._get_test_repository())
        self.test_job = None

    def tearDown(self):
        if self.test_job:
            if self.test_job.container:
                client = self.test_client()
                client.remove_container(self.test_job.container_id, force=True)
            self.test_job = None
        for d in [self.work_dir, self.resources_dir, self.output_dir]:
            if d:
                shutil.rmtree(d)

    def _create_test_job(self, script=TEST_SCRIPT, params=None):
        self.test_job = DockerJob(
            self.image, script, params,
            self.resources_dir, self.work_dir, self.output_dir)
        return self.test_job


class TestBaseDockerJob(TestDockerJob):
    """Tests Docker job using the base image golem/base"""

    def _get_test_repository(self):
        return "golem/base"

    def test_create(self):
        job = self._create_test_job()

        self.assertIsNone(job.container)
        self.assertEqual(job.state, DockerJob.STATE_NEW)
        self.assertIsNotNone(job.work_dir)
        self.assertIsNotNone(job.resources_dir)
        self.assertIsNotNone(job.output_dir)
        self.assertTrue(job._get_host_params_path().startswith(job.work_dir))
        self.assertTrue(job._get_host_script_path().startswith(job.work_dir))

    def _load_dict(self, path):
        with open(path, 'r') as f:
            lines = f.readlines()
        dict = {}
        for l in lines:
            key, val = l.split("=")
            dict[key.strip()] = eval(val.strip())
        return dict

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
        self._test_params_saved({"length": u"pięćdziesiąt łokci"})

    def _test_script_saved(self, task_script):
        with self._create_test_job(script=task_script) as job:
            script_path = job._get_host_script_path()
            self.assertTrue(path.isfile(script_path))
            with open(script_path, 'r') as f:
                script = unicode(f.read(), "utf-8")
            self.assertEqual(task_script, script)

    def test_script_saved(self):
        self._test_script_saved(TestDockerJob.TEST_SCRIPT)

    def test_script_saved_nonascii(self):
        self._test_script_saved(u"print u'Halo? Świeci!'\n")

    def test_container_created(self):
        with self._create_test_job() as job:
            self.assertIsNotNone(job.container_id)
            docker = self.test_client()
            info = docker.inspect_container(job.container_id)
            self.assertEqual(info["Id"], job.container_id)
            self.assertEqual(info["State"]["Status"], "created")
            self.assertFalse(info["State"]["Running"])

            image_id = docker.inspect_image(self.image.name)["Id"]
            self.assertEqual(info["Image"], image_id)

    def test_mounts(self):
        with self._create_test_job() as job:
            docker = self.test_client()
            info = docker.inspect_container(job.container_id)

            work_mount = None
            resources_mount = None
            output_mount = None
            for mount in info["Mounts"]:
                if mount["Destination"] == DockerJob.WORK_DIR:
                    work_mount = mount
                elif mount["Destination"] == DockerJob.RESOURCES_DIR:
                    resources_mount = mount
                elif mount["Destination"] == DockerJob.OUTPUT_DIR:
                    output_mount = mount

            work_dir = self.work_dir if not is_windows() \
                else nt_path_to_posix_path(self.work_dir)
            resource_dir = self.resources_dir if not is_windows() \
                else nt_path_to_posix_path(self.resources_dir)
            output_dir = self.output_dir if not is_windows()\
                else nt_path_to_posix_path(self.output_dir)

            self.assertIsNotNone(work_mount)
            self.assertEqual(work_mount["Source"], work_dir)
            self.assertTrue(work_mount["RW"])
            self.assertIsNotNone(resources_mount)
            self.assertEqual(resources_mount["Source"], resource_dir)
            self.assertFalse(resources_mount["RW"])
            self.assertIsNotNone(output_mount)
            self.assertEqual(output_mount["Source"], output_dir)
            self.assertTrue(output_mount["RW"])

    def test_cleanup(self):
        with self._create_test_job() as job:
            container_id = job.container_id
            self.assertIsNotNone(container_id)

        self.assertIsNone(job.container_id)
        with self.assertRaises(errors.NotFound):
            client = self.test_client()
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
            client = self.test_client()
            info = client.inspect_container(job.container_id)
            self.assertIn("Path", info)
            self.assertEqual(info["Path"], "/usr/bin/python")
            self.assertIn("Args", info)
            self.assertEqual(info["Args"], [job._get_container_script_path()])

    def test_logs_stdout(self):
        text = "Adventure Time!"
        src = "print '{}'\n".format(text)
        with self._create_test_job(script=src) as job:
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
        with self._create_test_job(script="syntax error!@#$%!") as job:
            job.start()
            err_file = path.join(self.output_dir, "stderr.log")
            job.dump_logs(stderr_file=err_file)
        out_files = os.listdir(self.output_dir)
        self.assertEqual(out_files, ["stderr.log"])
        with open(err_file, "r") as out:
            line = out.readline().strip()
        text = 'File "{}"'.format(job._get_container_script_path())
        self.assertTrue(line.startswith(text))

    def test_wait(self):
        src = "import time\ntime.sleep(5)\n"
        with self._create_test_job(script=src) as job:
            job.start()
            self.assertEqual(job.get_status(), DockerJob.STATE_RUNNING)
            exit_code = job.wait()
            self.assertEquals(exit_code, 0)
            self.assertEqual(job.get_status(), DockerJob.STATE_EXITED)

    def test_wait_timeout(self):
        src = "import time\ntime.sleep(10)\n"
        with self.assertRaises(requests.exceptions.ReadTimeout):
            with self._create_test_job(script=src) as job:
                job.start()
                self.assertEqual(job.get_status(), DockerJob.STATE_RUNNING)
                job.wait(1)

    def test_start_cleanup(self):
        # Ensure logging thread is created
        prev_level = container_logger.getEffectiveLevel()
        container_logger.setLevel(logging.DEBUG)
        with self._create_test_job() as job:
            job.start()
            self.assertIsNotNone(job.logging_thread)
            self.assertTrue(job.logging_thread.is_alive())
            job.wait()
        self.assertFalse(job.logging_thread.is_alive())
        container_logger.setLevel(prev_level)

    def test_logger_thread(self):
        # Ensure logging thread is created
        prev_level = container_logger.getEffectiveLevel()

        container_logger.setLevel(logging.DEBUG)
        with self._create_test_job() as job:
            job.start()
            self.assertIsNotNone(job.logging_thread)
            self.assertTrue(job.logging_thread.is_alive())
            job.wait()
        self.assertFalse(job.logging_thread.is_alive())

        container_logger.setLevel(logging.INFO)
        with self._create_test_job() as job:
            job.start()
            self.assertIsNone(job.logging_thread)
            job.wait()

        container_logger.setLevel(prev_level)

    def test_working_dir_set(self):
        script = "import os\nprint os.getcwd()\n"
        with self._create_test_job(script=script) as job:
            job.start()
            job.wait()
            out_file = path.join(self.output_dir, "stdout.log")
            job.dump_logs(stdout_file=out_file)
        with open(out_file, "r") as out:
            line = out.readline().strip()
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

        with open(path.join(self.resources_dir, "in.txt"), "w") as input:
            input.write(sample_text)

        with self._create_test_job(script=copy_script) as job:
            job.start()
            job.wait()

        outfile = path.join(self.output_dir, "out.txt")
        self.assertTrue(path.isfile(outfile))
        with open(outfile, "r") as f:
            text = f.read()
        self.assertEqual(text, sample_text)
