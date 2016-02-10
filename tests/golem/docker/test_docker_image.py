import unittest
from docker import Client
from docker import errors
import requests

from golem.task.docker.image import DockerImage


class DockerTestCase(unittest.TestCase):

    TEST_REPOSITORY = "imapp/blender"
    TEST_TAG = "latest"
    TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)
    TEST_IMAGE_ID = None

    @classmethod
    def setUpClass(cls):
        """Disable all tests if Docker or the test image is not available."""
        try:
            client = Client()
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
        client = Client()
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
        self.assertTrue(DockerImage.is_available(self.TEST_REPOSITORY))
        img = DockerImage(self.TEST_REPOSITORY)
        self.assertEqual(img.name, "{}:latest".format(self.TEST_REPOSITORY))

        self.assertFalse(DockerImage.is_available("imapp/xzy"))
        self.assertRaises(Exception, DockerImage, "imapp/xzy")

    def test_is_available_by_repo_and_tag(self):
        self.assertTrue(DockerImage.is_available(self.TEST_REPOSITORY,
                                                 tag=self.TEST_TAG))
        img = DockerImage(self.TEST_REPOSITORY, tag=self.TEST_TAG)
        self._is_test_image(img)

        self.assertFalse(
            DockerImage.is_available(self.TEST_REPOSITORY, tag="bogus"))
        self.assertRaises(Exception,
                          DockerImage, self.TEST_REPOSITORY, tag="bogus")

    def test_is_available_by_id(self):
        self.assertTrue(DockerImage.is_available(self.TEST_REPOSITORY,
                                                 id=self.TEST_IMAGE_ID))
        img = DockerImage(self.TEST_REPOSITORY, id=self.TEST_IMAGE_ID)
        self._is_test_image(img)

        self.assertFalse(DockerImage.is_available(self.TEST_REPOSITORY,
                                                  id="deadface"))
        self.assertRaises(Exception, DockerImage,
                          self.TEST_REPOSITORY, id="deadface")

    def test_is_available_by_id_and_tag(self):
        self.assertTrue(DockerImage.is_available(
            self.TEST_REPOSITORY, id=self.TEST_IMAGE_ID, tag=self.TEST_TAG))
        img = DockerImage(self.TEST_REPOSITORY, id=self.TEST_IMAGE_ID,
                          tag=self.TEST_TAG)
        self._is_test_image(img)

        self.assertFalse(DockerImage.is_available(
            self.TEST_REPOSITORY, id=self.TEST_IMAGE_ID, tag="bogus"))
        self.assertRaises(Exception, DockerImage, self.TEST_REPOSITORY,
                          id=self.TEST_IMAGE_ID, tag="bogus")
