from pathlib import Path
import json
import random
import shutil

import pytest

from apps.blender.resources.images.entrypoints.scripts.commands.create_task import create_task  # noqa
from apps.blender.resources.images.entrypoints.scripts.commands.get_subtask import get_subtask  # noqa
from apps.blender.resources.images.entrypoints.scripts.commands.compute import compute  # noqa
from apps.blender.resources.images.entrypoints.scripts.commands.verify import verify  # noqa
from apps.blender.resources.images.entrypoints.scripts.commands import utils
from golem.core.common import get_golem_path
from golem.testutils import TempDirFixture


@pytest.mark.skipif(
    shutil.which('blender') is None,
    reason='blender not available')
class TestCommands(TempDirFixture):

    def _make_req_dirs(self):
        req = self.new_path / f'req{random.random()}'
        req_work = req / 'work'
        req_resources = req / 'resources'
        req_net_resources = req / 'network_resources'
        req_results = req / 'results'
        req_net_results = req / 'network_results'
        for p in [req, req_work, req_resources, req_net_resources, req_results,
                  req_net_results]:
            p.mkdir()
        return req_work, req_resources, req_net_resources, req_results, \
            req_net_results

    def _make_prov_dirs(self):
        prov = self.new_path / f'prov{random.random()}'
        prov_work = prov / 'work'
        prov_net_resources = prov / 'network_resources'
        for p in [prov, prov_work, prov_net_resources]:
            p.mkdir()
        return prov_work, prov_net_resources

    @staticmethod
    def _put_cube_to_resources(req_resources: Path):
        shutil.copy2(
            Path(get_golem_path()) / 'apps' / 'blender' / 'benchmark' / 'test_task' / 'cube.blend',  # noqa
            req_resources,
        )

    @staticmethod
    def _dump_task_params(req_work: Path, task_params: dict):
        with open(req_work / 'task_params.json', 'w') as f:
            json.dump(task_params, f)

    @staticmethod
    def _copy_resources_from_requestor(
            req_net_resources: Path,
            prov_net_resources: Path,
            req_work: Path,
            prov_work: Path,
            subtask_id: str,
            subtask_params: dict):
        for resource_id in subtask_params['resources']:
            network_resource = req_net_resources / f'{resource_id}.zip'
            assert network_resource.exists()
            shutil.copy2(network_resource, prov_net_resources)
        shutil.copy2(
            req_work / f'subtask{subtask_id}.json',
            prov_work / 'params.json',
        )

    @staticmethod
    def _copy_result_from_provider(
            prov_work: Path,
            req_net_results: Path,
            subtask_id: str):
        result = prov_work / 'result.zip'
        assert result.exists()
        shutil.copy2(
            result,
            req_net_results / f'{subtask_id}.zip',
        )

    @staticmethod
    def _get_cube_params(subtasks_count: int, frames: str):
        return {
            "subtasks_count": subtasks_count,
            "format": "png",
            "resolution": [1000, 600],
            "frames": frames,
            "scene_file": "cube.blend",
            "resources": [
                "cube.blend",
            ]
        }

    def test_one_subtasks_one_frame(self):
        self._simulate(self._get_cube_params(1, "1"))

    def test_one_subtasks_three_frames(self):
        self._simulate(self._get_cube_params(1, "2-3;8"))

    def test_two_subtasks_one_frame(self):
        self._simulate(self._get_cube_params(2, "5"))

    def test_two_subtasks_two_frames(self):
        self._simulate(self._get_cube_params(2, "5;9"))

    def test_four_subtasks_two_frames(self):
        self._simulate(self._get_cube_params(4, "6-7"))

    def _simulate(self, task_params: dict):
        req_work, req_resources, req_net_resources, req_results, \
            req_net_results = self._make_req_dirs()

        self._put_cube_to_resources(req_resources)

        self._dump_task_params(req_work, task_params)
        create_task(req_work, req_resources, req_net_resources)

        for _ in range(task_params['subtasks_count']):
            prov_work, prov_net_resources = self._make_prov_dirs()

            subtask_id = get_subtask(req_work, req_resources, req_net_resources)
            with open(req_work / f'subtask{subtask_id}.json', 'r') as f:
                subtask_params = json.load(f)
            assert subtask_params['resources'] == [0]

            self._copy_resources_from_requestor(
                req_net_resources,
                prov_net_resources,
                req_work,
                prov_work,
                subtask_id,
                subtask_params,
            )

            compute(prov_work, prov_net_resources)
            self._copy_result_from_provider(
                prov_work,
                req_net_results,
                subtask_id,
            )

            verdict = verify(
                subtask_id,
                req_work,
                req_resources,
                req_net_resources,
                req_results,
                req_net_results,
            )
            assert verdict

        for frame in utils.string_to_frames(task_params['frames']):
            result_file = req_results / f'result{frame:04d}.{task_params["format"]}'  # noqa
            assert result_file.exists()
