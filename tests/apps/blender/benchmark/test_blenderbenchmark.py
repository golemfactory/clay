import os
import unittest
from unittest import mock

import pytest

from apps.blender.benchmark.benchmark import BlenderBenchmark
from apps.blender.dockerenvironment.blenderenvironment import BlenderEnvironment
from apps.blender.task import blenderrendertask
from apps.core.task.coretaskstate import TaskDesc
from apps.core.benchmark.benchmarkrunner import BenchmarkRunner
from apps.rendering.benchmark.renderingbenchmark import RenderingBenchmark
from apps.rendering.task.renderingtaskstate import RenderingTaskDefinition
from golem import testutils
from golem.network.p2p.node import Node
from golem.resource.dirmanager import DirManager
from golem.task.taskstate import TaskStatus
from golem.tools.ci import ci_skip


class TestBlenderBenchmark(unittest.TestCase, testutils.PEP8MixIn):
    PEP8_FILES = [
        "apps/blender/benchmark/benchmark.py",
    ]

    def setUp(self):
        self.bb = BlenderBenchmark(BlenderEnvironment())

    def test_is_instance(self):
        self.assertIsInstance(self.bb, BlenderBenchmark)
        self.assertIsInstance(self.bb, RenderingBenchmark)
        self.assertIsInstance(self.bb.task_definition, RenderingTaskDefinition)
        self.assertIsInstance(self.bb.task_definition.options,
                              blenderrendertask.BlenderRendererOptions)

    def test_task_settings(self):
        self.assertTrue(os.path.isdir(self.bb.blender_task_path))
        self.assertTrue(
            os.path.isfile(self.bb.task_definition.main_scene_file)
        )


@ci_skip
class TestBenchmarkRunner(testutils.TempDirFixture):

    @pytest.mark.slow
    def test_run(self):
        benchmark = BlenderBenchmark(BlenderEnvironment())
        task_definition = benchmark.task_definition

        task_state = TaskDesc()
        task_state.status = TaskStatus.notStarted
        task_state.definition = task_definition

        dir_manager = DirManager(self.path)
        task = blenderrendertask.BlenderRenderTaskBuilder(
            Node(),
            task_definition,
            dir_manager
        ).build()

        success = mock.MagicMock()
        error = mock.MagicMock()

        env_manager = mock.Mock()
        env_manager.get_environment_by_task_type.return_value = \
            BlenderEnvironment()
        br = BenchmarkRunner(task, env_manager, self.path, success, error,
                             benchmark)
        br.run()
        if br.tt:
            br.tt.join()

        self.assertEqual(success.call_count, 1)
