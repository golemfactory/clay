import requests
import unittest

from docker import Client
from docker.utils import kwargs_from_env

from golem.task.docker.image import DockerImage


class DockerTestCase(unittest.TestCase):

    TEST_REPOSITORY = "golem/base"
    TEST_TAG = "latest"
    TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)
    TEST_IMAGE_ID = None

    @classmethod
    def test_client(cls):
        return Client(**kwargs_from_env(assert_hostname=False))

    @classmethod
    def setUpClass(cls):
        """Disable all tests if Docker or the test image is not available."""
        try:
            client = cls.test_client()
            images = client.images()
            repo_tags = sum([img["RepoTags"] for img in images], [])
            if cls.TEST_IMAGE not in repo_tags:
                raise unittest.SkipTest(
                    "Skipping tests: Image {} not available".format(
                        cls.TEST_IMAGE))
            cls.TEST_IMAGE_ID = client.inspect_image(cls.TEST_IMAGE)["Id"]
        except requests.exceptions.ConnectionError:
            raise unittest.SkipTest(
                "Skipping tests: Cannot connect with Docker daemon")


class TestDockerImage(DockerTestCase):

    def tearDown(self):
        client = self.test_client()
        for c in client.containers(all=True):
            if c["Image"] == self.TEST_IMAGE:
                client.remove_container(c["Id"], force=True)

    def _is_test_image(self, img):
        self.assertEqual(img.name, self.TEST_IMAGE)
        if img.id:
            self.assertEqual(img.id, self.TEST_IMAGE_ID)
        self.assertEqual(img.repository, self.TEST_REPOSITORY)
        self.assertEqual(img.tag, self.TEST_TAG)

    def test_is_available_by_repo(self):
        img = DockerImage(self.TEST_REPOSITORY)
        self.assertTrue(img.is_available())
        self.assertEqual(img.name, "{}:latest".format(self.TEST_REPOSITORY))

        nimg = DockerImage("imapp/xzy")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_repo_and_tag(self):
        img = DockerImage(self.TEST_REPOSITORY, tag = self.TEST_TAG)
        self.assertTrue(img.is_available())
        self._is_test_image(img)

        nimg = DockerImage(self.TEST_REPOSITORY, tag = "bogus")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_id(self):
        img = DockerImage(self.TEST_REPOSITORY, id = self.TEST_IMAGE_ID)
        self.assertTrue(img.is_available)
        self._is_test_image(img)

        nimg = DockerImage(self.TEST_REPOSITORY, id = "deadface")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_id_and_tag(self):
        img = DockerImage(self.TEST_REPOSITORY, tag = self.TEST_TAG,
                          id = self.TEST_IMAGE_ID)
        self.assertTrue(img.is_available())

        nimg = DockerImage(self.TEST_REPOSITORY, tag = "bogus",
                           id = self.TEST_IMAGE_ID)
        self.assertFalse(nimg.is_available())

        nimg2 = DockerImage(self.TEST_REPOSITORY, tag = self.TEST_TAG,
                           id = "deadface")
        self.assertFalse(nimg2.is_available())

