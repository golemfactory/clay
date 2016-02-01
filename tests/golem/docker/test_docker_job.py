import glob
import os
from os import path
import shutil
import tempfile
from docker import Client
from docker import errors
import requests

from gnr.renderingdirmanager import find_task_script
from golem.core.common import get_golem_path
from golem.task.docker_job import DockerImage, DockerJob
from test_docker_image import DockerTestCase

TEST_REPOSITORY = "imapp/blender"
TEST_TAG = "latest"
TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)


class TestDockerJob(DockerTestCase):

    SCRIPT = """
    with open('/golem/output/hello.txt', 'w') as out:
        out.write('Hello from Golem!')
    """

    def setUp(self):
        self.resource_dir =  tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        self.image = DockerImage(TEST_REPOSITORY)

    def tearDown(self):
        if self.resource_dir:
            shutil.rmtree(self.resource_dir)
        if self.output_dir:
            shutil.rmtree(self.output_dir)

    def _create_test_job(self, script="", params=None):
        return DockerJob(self.image, script, params,
                         self.resource_dir, self.output_dir)

    def test_create(self):
        job = self._create_test_job()

        self.assertIsNone(job.task_dir)
        self.assertIsNone(job.container)
        self.assertEqual(job.state, DockerJob.STATE_NEW)

    def _test_prepared_job(self, job, src):
        task_dir = path.abspath(job.task_dir)
        self.assertIsNotNone(task_dir)
        self.assertTrue(path.isdir(task_dir))

        input_dir = path.abspath(job._get_input_dir())
        output_dir = path.abspath(job._get_output_dir())
        resource_dir = path.abspath(job._get_resource_dir())
        script_file = path.abspath(job._get_script_path())

        with open(script_file, "r") as f:
            test_src = f.read()
            self.assertEqual(src, test_src)

        self.assertTrue(path.isdir(input_dir))
        self.assertTrue(path.isdir(output_dir))
        self.assertTrue(path.isdir(resource_dir))
        self.assertTrue(path.isfile(script_file))

        self.assertTrue(input_dir.startswith(task_dir))
        self.assertTrue(output_dir.startswith(task_dir))
        self.assertTrue(resource_dir.startswith(task_dir))
        self.assertTrue(script_file.startswith(task_dir))

        self.assertIsNotNone(job.container)
        self.assertIsNotNone(job.container_id)

        client = Client()
        info = client.inspect_container(job.container_id)
        self.assertEqual(info["State"]["Status"], "created")
        self.assertFalse(info["State"]["Running"])

        image_id = client.inspect_image(self.image.name)["Id"]
        self.assertEqual(info["Image"], image_id)

        input_mount = None
        output_mount = None
        for mount in info["Mounts"]:
            if mount["Destination"] == DockerJob.DEST_INPUT_DIR:
                input_mount = mount
            elif mount["Destination"] == DockerJob.DEST_OUTPUT_DIR:
                output_mount = mount

        self.assertIsNotNone(input_mount)
        self.assertEqual(input_mount["Source"], input_dir)
        self.assertIsNotNone(output_mount)
        self.assertEqual(output_mount["Source"], output_dir)

        return task_dir

    def _test_cleanup(self, job, task_dir, container_id):
        self.assertFalse(path.isdir(task_dir))
        self.assertIsNone(job.task_dir)
        self.assertIsNone(job.container)
        try:
            client = Client()
            client.inspect_container(container_id)
            self.assertFalse("inspect_container should raise NotFound")
        except errors.NotFound:
            pass

    def test_prepare_cleanup(self):
        random_src = "# {} {}\n".format(self.resource_dir, self.output_dir)
        job = self._create_test_job(random_src)

        job._prepare()
        try:
            container_id = job.container_id
            task_dir = self._test_prepared_job(job, random_src)
        finally:
            job._cleanup()
        self._test_cleanup(job, task_dir, container_id)

    def test_with(self):
        random_src = "# {} {}\n".format(self.resource_dir, self.output_dir)

        with self._create_test_job(random_src) as job:
            task_dir = self._test_prepared_job(job, random_src)
            container_id = job.container_id

        self._test_cleanup(job, task_dir, container_id)

    def test_resource_copying(self):
        with open(path.join(self.resource_dir, "1.txt"), "w") as res1:
            res1.write("I am a text resource")
        dir2 = path.join(self.resource_dir, "2")
        os.mkdir(dir2)
        with open(path.join(dir2, "21.txt"), "w") as res2:
            res2.write("I am a text resource in a nested dir")
        dir22 = path.join(dir2, "2")
        os.mkdir(dir22)
        with open(path.join(dir22, "221.txt"), "w") as res3:
            res3.write("I am a text resource in a doubly nested dir")

        with self._create_test_job() as job:
            target_resource_dir = job._get_resource_dir()
            self.assertNotEqual(self.resource_dir, target_resource_dir)
            source_files = [(dirs, files)
                            for (_, dirs, files) in os.walk(self.resource_dir)]
            target_files = [(dirs, files)
                            for (_, dirs, files) in os.walk(target_resource_dir)]
            self.assertEqual(source_files, target_files)

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
            client = Client()
            info = client.inspect_container(job.container_id)
            self.assertIn("Path", info)
            self.assertEqual(info["Path"], "/usr/bin/python")
            self.assertIn("Args", info)
            self.assertEqual(info["Args"], [DockerJob.DEST_TASK_FILE])

    def test_wait(self):
        src = "import time\ntime.sleep(5)\n"
        with self._create_test_job(src) as job:
            job.start()
            self.assertEqual(job.get_status(), DockerJob.STATE_RUNNING)
            exit_code = job.wait()
            self.assertEquals(exit_code, 0)
            self.assertEqual(job.get_status(), DockerJob.STATE_EXITED)

    COPY_SCRIPT = """
with open("/golem/input/res/in.txt", "r") as f:
    text = f.read()

with open("/golem/output/out.txt", "w") as f:
    f.write(text)
"""

    def test_wait_timeout(self):
        src = "import time\ntime.sleep(10)\n"
        try:
            with self._create_test_job(src) as job:
                job.start()
                self.assertEqual(job.get_status(), DockerJob.STATE_RUNNING)
                job.wait(1)
                self.fail("Timeout expected")
        except requests.exceptions.ReadTimeout as e:
            pass

    def test_copy_job(self):
        """Creates a sample resource file and a task script that copies
        the resource file to the output file.
        """
        sample_text = "Hello!\n"

        with open(path.join(self.resource_dir, "in.txt"), "w") as input:
            input.write(sample_text)

        with self._create_test_job(self.COPY_SCRIPT) as job:
            job.start()
            job.wait()
            outfile = path.join(job._get_output_dir(), "out.txt")
            self.assertTrue(path.isfile(outfile))
            with open(outfile, "r") as f:
                text = f.read()
            self.assertEqual(text, sample_text)

    def test_get_output(self):
        sample_text = "Hello!\n"

        with open(path.join(self.resource_dir, "in.txt"), "w") as input:
            input.write(sample_text)

        with self._create_test_job(self.COPY_SCRIPT) as job:
            job.start()
            job.wait()

        outfile = path.join(self.output_dir, "out.txt")
        self.assertTrue(path.isfile(outfile))
        with open(outfile, "r") as f:
            text = f.read()
        self.assertEqual(text, sample_text)

    def test_blender_job(self):
        task_script = find_task_script("docker_blendertask.py")
        with open(task_script) as f:
            task_script_src = f.read()

        # copy the blender script to the resources dir
        crop_script = find_task_script("blendercrop.py")
        shutil.copy(crop_script, self.resource_dir)

        # copy the scene file to the resources dir
        benchmarks_dir = path.join(get_golem_path(),
                                   path.normpath("gnr/benchmarks/blender"))
        scene_files = glob.glob(path.join(benchmarks_dir, "**/*.blend"))
        if len(scene_files) == 0:
            self.fail("No .blend files available")
        shutil.copy(scene_files[0], self.resource_dir)

        params = {
            "outfilebasename": "out",
            "scene_file": "res/" + path.basename(scene_files[0]),
            "script_file": "res/" + path.basename(crop_script),
            "start_task": 42,
            "engine": "BLENDER",
            "frames": [1]
        }

        with self._create_test_job(task_script_src, params) as job:
            job.start()
            exit_code = job.wait()
            if exit_code is not 0:
                print job.get_logs()
            self.assertEqual(exit_code, 0)






