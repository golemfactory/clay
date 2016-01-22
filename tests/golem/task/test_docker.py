import unittest
from docker import Client
from docker import errors

from golem.task.docker_image import DockerImage


class DockerTest(unittest.TestCase):
    """TODO: Mock docker client in this test case"""

    TEST_REPOSITORY = "hello-world"

    def setUp(self):
        client = Client()
        try:
            info = client.inspect_image(self.TEST_REPOSITORY)
        except errors.NotFound:
            client.pull(self.TEST_REPOSITORY, stream=False)
            info = client.inspect_image(self.TEST_REPOSITORY)

        self.test_image_id = info["Id"]
        print "test image id: ", self.test_image_id

    def test_is_available_by_repo(self):
        img = DockerImage(self.TEST_REPOSITORY)
        self.assertTrue(img.is_available())

        img = DockerImage("imapp/xyz")
        self.assertFalse(img.is_available())

    def test_is_available_by_id(self):
        img = DockerImage(self.TEST_REPOSITORY, self.test_image_id)
        self.assertTrue(img.is_available())

        img = DockerImage(self.TEST_REPOSITORY, id="deadface")
        self.assertFalse(img.is_available())
