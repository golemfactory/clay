import os
from unittest import TestCase

import apps.lux.resources.scenefilereader as sfr

from golem.core.common import get_golem_path


def get_benchmark_scene():
    scene_path = os.path.join(get_golem_path(), "apps", "lux", "benchmark",
                              "test_task", "schoolcorridor.lxs")
    with open(scene_path) as f:
        scene = f.read()
    return scene


class TestScenFileReader(TestCase):
    def test_get_resolution(self):
        scene_file_src = 'Film "fleximage"\n "bool write_exr" ["true"]\n ' \
                         '"integer xresolution" [200] ' \
                         '"integer yresolution" [100]\n ' \
                         '"integer writeinterval" [15]\n ' \
                         '"float cropwindow" [0, 1, 0, 1]'
        assert sfr.get_resolution(scene_file_src) == (200, 100)
        scene_file_src = "no resultion"
        assert sfr.get_resolution(scene_file_src) is None

        scene_file_src = 'Film "fleximage"\n "bool write_exr" ["true"]\n ' \
                         '"integer yresolution" [100]\n ' \
                         '"integer writeinterval" [15]\n ' \
                         '"float cropwindow" [0, 1, 0, 1]'

        assert sfr.get_resolution(scene_file_src) is None

        scene_file_src = 'Film "fleximage"\n "bool write_exr" ["true"]\n ' \
                         '"integer xresolution" [200]\n ' \
                         '"integer writeinterval" [15]\n ' \
                         '"float cropwindow" [0, 1, 0, 1]'

        assert sfr.get_resolution(scene_file_src) is None

        assert sfr.get_resolution(get_benchmark_scene()) == (201, 268)

    def test_get_filename(self):
        assert sfr.get_filename(get_benchmark_scene()) == \
               "LuxRender08_test_scene.Scene.00001"

        assert sfr.get_filename("no filename") is None

    def test_get_file_format(self):
        assert sfr.get_file_format(get_benchmark_scene()) == ".png"

        assert sfr.get_file_format("no filename") is None

    def test_get_haltspp(self):
        assert sfr.get_haltspp(get_benchmark_scene()) == 5
        assert sfr.get_haltspp("no haltspp") is None
