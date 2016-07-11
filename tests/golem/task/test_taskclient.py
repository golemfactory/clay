import unittest
import uuid

from golem.task.taskclient import TaskClient


class TestTaskClient(unittest.TestCase):
    def test(self):

        node_id = str(uuid.uuid4())
        node_dict = {}

        tc = TaskClient.assert_exists(node_id, node_dict)
        assert tc
        assert node_id in node_dict

        tc.start()
        assert tc.started()
        tc.finish()
        assert tc.finishing()

        tc.accept()
        assert not tc.started()
        assert not tc.finishing()
        assert tc.accepted()

        tc.reject()
        assert tc.rejected()
