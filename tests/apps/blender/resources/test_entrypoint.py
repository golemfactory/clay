from apps.blender.resources.images.commands.create_task import create_task
from apps.blender.resources.images.commands.get_subtask import get_subtask
from apps.blender.resources.images.commands.compute import compute
from apps.blender.resources.images.commands.verify import verify

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
        subtask_id = get_subtask(
            self.req_work,
            self.req_resources,
            self.req_net_resources,
        )
        with open(self.req_work / f'subtask{subtask_id}.json', 'r') as f:
            subtask_params = json.load(f)
        assert subtask_params['resources'] == [0]
        network_resource = self.req_net_resources / '0.zip'
        assert network_resource.exists()
        shutil.copy2(network_resource, self.prov_net_resources)
        shutil.copy2(
            self.req_work / f'subtask{subtask_id}.json',
            self.prov_work / 'params.json',
        )

        compute(
            self.prov_work,
            self.prov_net_resources,
        )

        result = self.prov_work / 'result.zip'
        assert result.exists()
        shutil.copy2(
            result,
            self.req_net_results / f'{subtask_id}.zip',
        )

        verify(
            self.req_work,
            self.req_resources,
            self.req_net_resources,
            self.req_results,
            self.req_net_results,
        )
