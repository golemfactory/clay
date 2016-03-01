import jsonpickle
import logging
import unittest

from golem.core.common import get_golem_path
import gnr.node
from gnr.task.blenderrendertask import BlenderRenderTaskBuilder


# Make peewee logging less verbose
logging.getLogger("peewee").setLevel("INFO")


TASK_FILE = "docker-blender-test-task.json"


class TestDockerBlenderTask(unittest.TestCase):

    def setUp(self):
        self.node = gnr.node.GNRNode()
        self.node.initialize()

    def tearDown(self):
        self.node.client.quit()

    def test_start_stop(self):
        pass

    def _test_task_definition(self):
        with open(TASK_FILE, "r") as f:
            task_def = jsonpickle.decode(f.read())
        return task_def

    def test_docker_task(self):
        node_name = "0123456789abcdef"
        task_def = self._test_task_definition()
        root_path = get_golem_path()

        task_builder = BlenderRenderTaskBuilder(node_name, task_def, root_path)
        render_task = task_builder.build()
        render_task.__class__._update_task_preview = lambda s: ()
        ctd = render_task.query_extra_data(1.0)

        task_computer = self.node.client.task_server.task_computer
        subtask_timeout = 600
        task_computer.task_given(ctd, subtask_timeout)
        task_computer.resource_given(ctd.task_id)

