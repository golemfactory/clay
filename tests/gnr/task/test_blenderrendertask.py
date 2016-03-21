import unittest
import os

from gnr.task.blenderrendertask import (BlenderDefaults, BlenderRenderTaskBuilder, BlenderRenderTask,
                                        BlenderRendererOptions)
from gnr.renderingtaskstate import RenderingTaskDefinition
from golem.tools.testdirfixture import TestDirFixture


class TestBlenderDefaults(unittest.TestCase):
    def test_init(self):
        bd = BlenderDefaults()
        self.assertTrue(os.path.isfile(bd.main_program_file))


class TestBlenderRenderTaskBuilder(TestDirFixture):
    def test_build(self):
        definition = RenderingTaskDefinition()
        definition.renderer_options = BlenderRendererOptions()
        builder = BlenderRenderTaskBuilder(node_name="ABC", task_definition=definition, root_path=self.path)
        blender_task = builder.build()
        self.assertIsInstance(blender_task, BlenderRenderTask)
