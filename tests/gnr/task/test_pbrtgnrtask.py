from os import path
from unittest import TestCase

from gnr.gnrtaskstate import GNRTaskDefinition
from gnr.task.pbrtgnrtask import PbrtDefaults, PbrtGNRTaskBuilder, PbrtRenderTask, PbrtRendererOptions
from golem.tools.testdirfixture import TestDirFixture


class TestPbrtDefaults(TestCase):
    def test_init(self):
        pd = PbrtDefaults()
        self.assertTrue(path.isfile(pd.main_program_file))


class TestPbrtGNRTaskBuilder(TestDirFixture):
    def test_build(self):
        definition = GNRTaskDefinition()
        definition.max_price = 31.2
        definition.options = PbrtDefaults()
        definition.options.main_scene_file = "somefile"
        definition.options.output_file = "anotherfile"
        definition.options.pbrt_path = ""
        definition.options.pixel_filter = ""
        definition.options.samples_per_pixel_count = 32
        definition.options.algorithm_type = ""
        builder = PbrtGNRTaskBuilder("ABC", definition, self.path)
        task = builder.build()
        self.assertIsInstance(task, PbrtRenderTask)
        self.assertEqual(task.header.max_price, 31.2)
