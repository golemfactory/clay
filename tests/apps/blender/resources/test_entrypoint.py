from apps.blender.resources.images.commands.create_task import create_task

from golem.testutils import TempDirFixture
from golem.core.common import get_golem_path

import json
import shutil
from pathlib import Path


TASK_PARAMS = {
    "subtasks_count": 4,
    "format": "PNG",
    "resolution": [1000, 600],
    "frames": "1-2",
    "resources": [
        "cube.blend",
    ]
}


class TestCommands(TempDirFixture):
    def setUp(self):
        super().setUp()
        self.req = self.new_path / 'req'
        self.req_work = self.req / 'work'
        self.req_resources = self.req / 'resources'
        self.req_net_resources = self.req / 'network_resources'
        self.req_results = self.req / 'results'
        self.req_net_results = self.req / 'network_results'

        self.prov = self.new_path / 'prov'
        self.prov_work = self.prov / 'work'
        self.prov_net_resources = self.prov / 'network_resources'

        for p in [self.req, self.req_work, self.req_resources, self.req_results,
                  self.req_net_resources, self.req_net_results, self.prov,
                  self.prov_work, self.prov_net_resources]:
            p.mkdir()

    def test_basic(self):
        shutil.copy2(
            Path(get_golem_path()) / 'apps' / 'blender' / 'benchmark' / 'test_task' / 'cube.blend',  # noqa
            self.req_resources,
        )
        with open(self.req_work / 'task_params.json', 'w') as f:
            json.dump(TASK_PARAMS, f)
        create_task(
            self.req_work,
            self.req_resources,
            self.req_net_resources,
        )
