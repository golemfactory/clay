from os import mkdir, path, walk
import shutil
import tempfile
import unittest
from docker import Client
from docker import errors
import requests

from golem.task.docker_job import DockerImage, DockerJob


TEST_REPOSITORY = "imapp/blender"
TEST_TAG = "latest"
TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)


class TestDockerJob(unittest.TestCase):

    SCRIPT = """
    with open('/golem/output/hello.txt', 'w') as out:
        out.write('Hello from Golem!')
    """

    @classmethod
    def setUpClass(cls):
        """Disable all the tests if docker is not available"""
        try:
            client = Client()
            images = client.images()
            repo_tags = sum([img["RepoTags"] for img in images], [])
            if TEST_IMAGE not in repo_tags:
                assert False, "Docker image {} is not available".format(
                    TEST_IMAGE)
        except requests.exceptions.ConnectionError:
            assert False, "Docker daemon is not running"
            #TODO: skip all tests without reporting failure

    def setUp(self):
        self.resource_dir = None
        self.output_dir = None

    def tearDown(self):
        if self.resource_dir:
            shutil.rmtree(self.resource_dir)
        if self.output_dir:
            shutil.rmtree(self.output_dir)

    def _create_dirs(self):
        self.resource_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()
        return self.resource_dir, self.output_dir

    def test_create(self):
        res_dir, out_dir = self._create_dirs()

        img = DockerImage(TEST_REPOSITORY)
        job = DockerJob(img, self.SCRIPT, res_dir, out_dir)

        self.assertIsNone(job.task_dir)
        self.assertIsNone(job.container)
        self.assertEqual(job.state, DockerJob.STATE_NEW)

    def _test_prepared_job(self, job, src, img):
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

        image_id = client.inspect_image(img.name)["Id"]
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
        res_dir, out_dir = self._create_dirs()

        img = DockerImage(TEST_REPOSITORY)
        src = "# {} {}\n".format(res_dir, out_dir)  # some random-ish text
        job = DockerJob(img, src, res_dir, out_dir)

        job._prepare()
        try:
            container_id = job.container_id
            task_dir = self._test_prepared_job(job, src, img)
        finally:
            job._cleanup()
        self._test_cleanup(job, task_dir, container_id)

    def test_with(self):
        res_dir, out_dir = self._create_dirs()

        img = DockerImage(TEST_REPOSITORY)
        src = "# {} {}\n".format(res_dir, out_dir)  # some random-ish text

        with DockerJob(img, src, res_dir, out_dir) as job:
            task_dir = self._test_prepared_job(job, src, img)
            container_id = job.container_id

        self._test_cleanup(job, task_dir, container_id)

    def test_resource_copying(self):
        resource_dir, output_dir = self._create_dirs()

        img = DockerImage(TEST_REPOSITORY)
        with open(path.join(resource_dir, "1.txt"), "w") as res1:
            res1.write("I am a text resource")
        dir2 = path.join(resource_dir, "2")
        mkdir(dir2)
        with open(path.join(dir2, "21.txt"), "w") as res2:
            res2.write("I am a text resource in a nested dir")
        dir22 = path.join(dir2, "2")
        mkdir(dir22)
        with open(path.join(dir22, "221.txt"), "w") as res3:
            res3.write("I am a text resource in a doubly nested dir")

        with DockerJob(img, "", resource_dir, output_dir) as job:
            target_resource_dir = job._get_resource_dir()
            self.assertNotEqual(resource_dir, target_resource_dir)
            source_files = [(dirs, files)
                            for (_, dirs, files) in walk(resource_dir)]
            target_files = [(dirs, files)
                            for (_, dirs, files) in walk(target_resource_dir)]
            self.assertEqual(source_files, target_files)

    def test_status(self):
        resource_dir, output_dir = self._create_dirs()
        img = DockerImage(TEST_REPOSITORY)

        job = DockerJob(img, "", resource_dir, output_dir)
        self.assertEqual(job.get_status(), DockerJob.STATE_NEW)
        job._prepare()
        self.assertEqual(job.get_status(), DockerJob.STATE_CREATED)
        job.start()
        self.assertTrue(job.get_status() in
                        [DockerJob.STATE_EXITED, DockerJob.STATE_RUNNING])
        job._cleanup()
        self.assertEqual(job.state, DockerJob.STATE_REMOVED)

        with DockerJob(img, "", resource_dir, output_dir) as job2:
            self.assertEqual(job2.get_status(), DockerJob.STATE_CREATED)
        self.assertEqual(job2.get_status(), DockerJob.STATE_REMOVED)

    def test_start(self):
        resource_dir, output_dir = self._create_dirs()
        img = DockerImage(TEST_REPOSITORY)

        with DockerJob(img, "", resource_dir, output_dir) as job:
            job.start()
            client = Client()
            info = client.inspect_container(job.container_id)
            self.assertIn("Path", info)
            self.assertEqual(info["Path"], "/usr/bin/python")
            self.assertIn("Args", info)
            self.assertEqual(info["Args"], [DockerJob.DEST_TASK_FILE])

    def test_wait(self):
        resource_dir, output_dir = self._create_dirs()
        img = DockerImage(TEST_REPOSITORY)
        src = "import time\ntime.sleep(5)\n"
        with DockerJob(img, src, resource_dir, output_dir) as job:
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

    def test_copy_input(self):
        """Creates a sample resource file and a task script that copies
        the resource file to the output file.
        """
        resource_dir, output_dir = self._create_dirs()
        img = DockerImage(TEST_REPOSITORY)
        sample = "Hello!\n"

        with open(path.join(resource_dir, "in.txt"), "w") as input:
            input.write(sample)

        with DockerJob(img, self.COPY_SCRIPT, resource_dir, output_dir) as job:
            job.start()
            job.wait()
            outfile = path.join(job._get_output_dir(), "out.txt")
            self.assertTrue(path.isfile(outfile))
            with open(outfile, "r") as f:
                text = f.read()
            self.assertEqual(text, sample)

    def test_get_output(self):
        resource_dir, output_dir = self._create_dirs()
        img = DockerImage(TEST_REPOSITORY)
        sample = "Hello!\n"

        with open(path.join(resource_dir, "in.txt"), "w") as input:
            input.write(sample)

        with DockerJob(img, self.COPY_SCRIPT, resource_dir, output_dir) as job:
            job.start()
            job.wait()

        outfile = path.join(output_dir, "out.txt")
        self.assertTrue(path.isfile(outfile))
        with open(outfile, "r") as f:
            text = f.read()
        self.assertEqual(text, sample)
