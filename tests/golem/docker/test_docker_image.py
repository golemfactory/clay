import unittest
from docker import Client
from docker import errors
import requests

from golem.task.docker_job import DockerImage


TEST_REPOSITORY = "imapp/blender"
TEST_TAG = "latest"
TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)


class DockerTestCase(unittest.TestCase):
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
            raise unittest.SkipTest(
                "Skipping tests: Cannot connect with Docker daemon")


class TestDockerImage(DockerTestCase):
    """TODO: Mock docker client in this test case"""

    def setUp(self):
        client = Client()
        self.image_name = TEST_IMAGE
        try:
            info = client.inspect_image(self.image_name)
        except errors.NotFound:
            client.pull(TEST_REPOSITORY, stream=False)
            info = client.inspect_image(TEST_REPOSITORY)

        self.image_id = info["Id"]

    def tearDown(self):
        client = Client()
        for c in client.containers(all=True):
            if c["Image"] == self.image_name:
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
