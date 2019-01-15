import unittest

import requests
from docker import errors

from golem.docker.client import local_client
from golem.docker.image import DockerImage
from golem.tools.ci import ci_skip


class DockerTestCase(unittest.TestCase):

    TEST_REPOSITORY = "golemfactory/base"
    TEST_TAG = "1.4"
    TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)
    TEST_ENV_ID = None

    @classmethod
    def setUpClass(cls):
        """Disable all tests if Docker or the test image is not available."""
        try:
            client = local_client()
            images = client.images()
            repo_tags = sum([img["RepoTags"]
                             for img in images
                             if img["RepoTags"]], [])
            if cls.TEST_IMAGE not in repo_tags:
                raise unittest.SkipTest(
                    "Skipping tests: Image {} not available".format(
                        cls.TEST_IMAGE))
            cls.TEST_ENV_ID = client.inspect_image(cls.TEST_IMAGE)["Id"]
        except (requests.exceptions.ConnectionError, errors.DockerException):
            raise unittest.SkipTest(
                "Skipping tests: Cannot connect with Docker daemon")


@ci_skip
class TestDockerImage(DockerTestCase):

    def tearDown(self):
        client = local_client()
        for c in client.containers(all=True):
            if c["Image"] == self.TEST_IMAGE:
                client.remove_container(c["Id"], force=True)

    def _is_test_image(self, img):
        self.assertEqual(img.name, self.TEST_IMAGE)
        if img.id:
            self.assertEqual(img.id, self.TEST_ENV_ID)
        self.assertEqual(img.repository, self.TEST_REPOSITORY)
        self.assertEqual(img.tag, self.TEST_TAG)

    def test_is_available_by_repo(self):
        # img = DockerImage(repository=self.TEST_REPOSITORY,
        #                   tag=self.TEST_TAG)
        # self.assertTrue(img.is_available())
        # self.assertEqual(img.name, "{}:{}".format(self.TEST_REPOSITORY,
        #                                           self.TEST_TAG))

        nimg = DockerImage("imapp/xzy")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_repo_and_tag(self):
        img = DockerImage(self.TEST_REPOSITORY, tag=self.TEST_TAG)
        self.assertTrue(img.is_available())
        self._is_test_image(img)

        nimg = DockerImage(self.TEST_REPOSITORY, tag="bogus")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_id(self):
        # img = DockerImage(self.TEST_REPOSITORY, image_id=self.TEST_ENV_ID)
        # self.assertTrue(img.is_available)
        # self._is_test_image(img)

        nimg = DockerImage(self.TEST_REPOSITORY, image_id="deadface")
        self.assertFalse(nimg.is_available())

    def test_is_available_by_id_and_tag(self):
        img = DockerImage(self.TEST_REPOSITORY, tag=self.TEST_TAG,
                          image_id=self.TEST_ENV_ID)
        self.assertTrue(img.is_available())

        nimg = DockerImage(self.TEST_REPOSITORY, tag="bogus",
                           image_id=self.TEST_ENV_ID)
        self.assertFalse(nimg.is_available())

        nimg2 = DockerImage(self.TEST_REPOSITORY, tag=self.TEST_TAG,
                            image_id="deadface")
        self.assertFalse(nimg2.is_available())

    def test_cmp_name_and_tag(self):

        img = DockerImage(self.TEST_REPOSITORY,
                          tag=self.TEST_TAG,
                          image_id=self.TEST_ENV_ID)
        img2 = DockerImage(self.TEST_REPOSITORY, tag=self.TEST_TAG)
        
        assert img.cmp_name_and_tag(img2)
        assert img2.cmp_name_and_tag(img)

        img3 = DockerImage(self.TEST_REPOSITORY,
                           tag="bogus",
                           image_id=self.TEST_ENV_ID)
        assert not img.cmp_name_and_tag(img3)
        assert not img3.cmp_name_and_tag(img)

        img4 = DockerImage("golemfactory/xyz",
                           tag=self.TEST_TAG,
                           image_id=self.TEST_ENV_ID)
        assert not img.cmp_name_and_tag(img4)
        assert not img4.cmp_name_and_tag(img)
