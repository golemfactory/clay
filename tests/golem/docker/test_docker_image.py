import shutil
import os
import tempfile
import unittest

import requests
from docker import Client
from docker.utils import kwargs_from_env

from golem.docker.image import DockerImage
from golem.tools.ci import ci_skip, in_circleci


def _count_containers(client):
    return len(client.containers(all=True))


class DockerTestCase(unittest.TestCase):

    TEST_REPOSITORY = "golemfactory/base"
    TEST_TAG = "1.2"
    BLENDER_IMAGE_REP = 'golemfactory/blender'
    BLENDER_IMAGE_TAG = '1.4'
    TEST_IMAGE = "{}:{}".format(TEST_REPOSITORY, TEST_TAG)
    TEST_ENV_ID = None

    @classmethod
    def test_client(cls):
        return Client(**kwargs_from_env(assert_hostname=False))

    @classmethod
    def setUpClass(cls):
        """Disable all tests if Docker or the test image is not available."""
        try:
            client = cls.test_client()
            images = client.images()
            repo_tags = sum([img["RepoTags"]
                             for img in images
                             if img["RepoTags"]], [])
            if cls.TEST_IMAGE not in repo_tags:
                raise unittest.SkipTest(
                    "Skipping tests: Image {} not available".format(
                        cls.TEST_IMAGE))
            cls.TEST_ENV_ID = client.inspect_image(cls.TEST_IMAGE)["Id"]
        except requests.exceptions.ConnectionError:
            raise unittest.SkipTest(
                "Skipping tests: Cannot connect with Docker daemon")


@ci_skip
class TestDockerImage(DockerTestCase):

    def tearDown(self):
        client = self.test_client()
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

    def test_path_extraction(self):
        img = DockerImage(self.BLENDER_IMAGE_REP, tag=self.BLENDER_IMAGE_TAG)
        client = self.test_client()
        num_containers_before = _count_containers(client)
        try:
            target_dir = tempfile.TemporaryDirectory(
                prefix='blender_extraction_test_',
                dir='/tmp'
            ).name
            blender_dir = os.path.join(target_dir, 'blender')
            blender_binary = os.path.join(blender_dir, 'blender')
            img.extract_path('/opt/blender/', target_dir)
            self.assertTrue(os.path.isfile(blender_binary))
        finally:
            shutil.rmtree(target_dir, ignore_errors=True)
            if not in_circleci():
                self.assertEqual(num_containers_before,
                                 _count_containers(client))

    def test_path_extraction_of_non_existent_path_fails_gracefully(self):
        img = DockerImage(self.BLENDER_IMAGE_REP, tag=self.BLENDER_IMAGE_TAG)
        client = self.test_client()
        num_containers_before = _count_containers(client)
        non_existent_container_path = '/opt/should_not/exist_in_/the_container'
        try:
            img.extract_path(non_existent_container_path, '/tmp')
            self.fail('Extracting a non-existent path should raise '
                      'an exception')
        except OSError as e:
            self.assertIn(non_existent_container_path, str(e))
            if not in_circleci():
                self.assertEqual(num_containers_before,
                                 _count_containers(client))

    def test_path_extraction_to_a_permissions_restricted_path_fails_fine(self):
        local_path_we_have_no_write_permissions_to = '/root'
        if os.access(local_path_we_have_no_write_permissions_to, os.W_OK):
            self.skipTest('Environmental prerequisites for this test not met.')
        img = DockerImage(self.BLENDER_IMAGE_REP, tag=self.BLENDER_IMAGE_TAG)
        client = self.test_client()
        num_containers_before = _count_containers(client)
        try:
            img.extract_path(
                '/opt/blender/',
                local_path_we_have_no_write_permissions_to
            )
            self.fail('Extracting to a path without write permissions '
                      'should raise an exception!')
        except PermissionError as pe:
            self.assertIn(local_path_we_have_no_write_permissions_to, str(pe))
            if not in_circleci():
                self.assertEqual(num_containers_before,
                                 _count_containers(client))
