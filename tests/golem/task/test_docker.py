import shutil
import tempfile
import unittest
from docker import Client
from docker import errors

from golem.task.docker_job import DockerImage, DockerJob


TEST_REPOSITORY = "imapp/blender" #" hello-world"
TEST_TAG = "latest"


class TestDockerImage(unittest.TestCase):
    """TODO: Mock docker client in this test case"""

    def setUp(self):
        client = Client()
        self.image_name = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)
        try:
            info = client.inspect_image(self.image_name)
        except errors.NotFound:
            client.pull(TEST_REPOSITORY, stream=False)
            info = client.inspect_image(TEST_REPOSITORY)

        self.image_id = info["Id"]
        print "test image id: ", self.image_id

    def tearDown(self):
        client = Client()
        for c in client.containers(all=True):
            if c["Image"] == self.image_name:
                print "removing container ", c["Id"]
                client.remove_container(c["Id"], force=True)

    def test_is_available_by_repo(self):
        self.assertTrue(DockerImage.is_available(TEST_REPOSITORY))
        img = DockerImage(TEST_REPOSITORY)
        self.assertEqual(img.name, self.image_name)

        self.assertFalse(DockerImage.is_available("imapp/xzy"))
        self.assertRaises(Exception, DockerImage, "imapp/xzy")

    def test_is_available_by_repo_and_tag(self):
        self.assertTrue(DockerImage.is_available(TEST_REPOSITORY, tag="latest"))
        img = DockerImage(TEST_REPOSITORY, tag="latest")
        self.assertEqual(img.name, self.image_name)

        self.assertFalse(DockerImage.is_available(TEST_REPOSITORY, tag="bogus"))
        self.assertRaises(Exception, DockerImage, TEST_REPOSITORY, tag="bogus")

    def test_is_available_by_id(self):
        self.assertTrue(DockerImage.is_available(
            TEST_REPOSITORY, id=self.image_id))
        img = DockerImage(TEST_REPOSITORY, id=self.image_id)
        self.assertEqual(img.name, self.image_name)
        self.assertEqual(img.id, self.image_id)

        self.assertFalse(DockerImage.is_available(
            TEST_REPOSITORY, id="deadface"))
        self.assertRaises(Exception, DockerImage,
                          TEST_REPOSITORY, id="deadface")

    def test_is_available_by_id_and_tag(self):
        self.assertTrue(DockerImage.is_available(
            TEST_REPOSITORY, id=self.image_id, tag=TEST_TAG))
        img = DockerImage(TEST_REPOSITORY, id=self.image_id, tag=TEST_TAG)
        self.assertEqual(img.name, self.image_name)
        self.assertEqual(img.id, self.image_id)

        self.assertFalse(DockerImage.is_available(
            TEST_REPOSITORY, id=self.image_id, tag="bogus"))
        self.assertRaises(Exception, DockerImage,
                          TEST_REPOSITORY, id=self.image_id, tag="bogus")


class TestDockerJob(unittest.TestCase):

    SCRIPT = """
    with open('/golem/output/hello.txt', 'w') as out:
        out.write('Hello from Golem!')
    """

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
        self.assertEqual(job.state, DockerJob.STATE_CREATED)
        job.cleanup()


    # def test_container_create(self):
    #     img = DockerImage(TEST_REPOSITORY)
    #     cont = DockerContainer(img, detached=True)
    #     self.assertTrue(cont.container_id is not None)
    #
    # def test_container_remove(self):
    #     img = DockerImage(TEST_REPOSITORY)
    #     cont = DockerContainer(img, detached=True)
    #     cont.remove()
    #
    # def test_start(self):
    #     img = DockerImage(TEST_REPOSITORY)
    #     cont = DockerContainer(img, detached=True)
    #     cont.start()
    #
    # def test_container_get_status(self):
    #     img = DockerImage(TEST_REPOSITORY)
    #     cont = DockerContainer(img, detached=True)
    #     self.assertEqual(cont.get_status(), DockerContainer.STATE_CREATED)
    #     cont.start()
    #     self.assertEqual(cont.get_status(), DockerContainer.STATE_RUNNING)
    #     cont.remove()
    #     self.assertEqual(cont.get_status(), DockerContainer.STATE_REMOVED)
    #
    # def test_is_running(self):
    #     img = DockerImage(TEST_REPOSITORY)
    #     cont = DockerContainer(img, detached=True)
    #     self.assertFalse(cont.is_running())
    #     cont.start()
    #     self.assertTrue(cont.is_running())
    #     cont.remove()
    #
