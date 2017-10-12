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

    def test_get_random_crop_window_for_verification(self):

        src = '# Main Scene File\n\nRenderer "sampler"\n\n#Sampler "lowdiscrepancy"\n#\t"integer pixelsamples" [4]\n\nSampler "metropolis"\n\t"float largemutationprob" [0.400000005960464]\n\t"bool usevariance" ["false"]\n\nAccelerator "qbvh"\n\nSurfaceIntegrator "bidirectional"\n\t"integer eyedepth" [16]\n\t"integer lightdepth" [16]\n\nVolumeIntegrator "multi"\n\t"float stepsize" [1.000000000000000]\n\nPixelFilter "mitchell"\n\t"bool supersample" ["true"]\n\nLookAt -0.315666 -0.074268 1.700000 -0.414931 -0.065879 1.691284 -0.008685 0.000734 0.099619\n\nCamera "perspective"\n\t"float fov" [56.144978015299799]\n\t"float screenwindow" [-0.750000000000000 0.750000000000000 -1.000000000000000 1.000000000000000]\n\t"bool autofocus" ["false"]\n\t"float shutteropen" [0.000000000000000]\n\t"float shutterclose" [0.040000000000000]\n\t"float focaldistance" [4.000000000000000]\n\nFilm "fleximage"\n\t"integer xresolution" [300]\n\t"integer yresolution" [400]\n' \
              '\t"float cropwindow" [0.2 0.4 0.7 0.9] \n' \
              '\t"float gamma" [2.200000000000000]\n\t"float colorspace_white" [0.314275000000000 0.329411000000000]\n\t"float colorspace_red" [0.630000000000000 0.340000000000000]\n\t"float colorspace_green" [0.310000000000000 0.595000000000000]\n\t"float colorspace_blue" [0.155000000000000 0.070000000000000]\n\t"string cameraresponse" ["Gold_100CD"]\n\t"string filename" ["LuxRender08_test_scene.Scene.00001"]\n\t"bool write_resume_flm" ["false"]\n\t"bool restart_resume_flm" ["false"]\n\t"bool write_exr_applyimaging" ["true"]\n\t"bool write_exr" ["false"]\n\t"bool write_png" ["true"]\n\t"string write_png_channels" ["RGB"]\n\t"bool write_tga" ["false"]\n\t"string ldr_clamp_method" ["lum"]\n\t"integer displayinterval" [10]\n\t"integer writeinterval" [120]\n\t"integer outlierrejection_k" [1]\n\t"integer haltspp" [25]\n\t"string tonemapkernel" ["reinhard"]\n\t"float reinhard_prescale" [1.000000000000000]\n\t"float reinhard_postscale" [1.200000047683716]\n\t"float reinhard_burn" [8.000000000000000]\n\nWorldBegin\n\nInclude "LuxRender08_test_scene/Scene/00001/LuxRender-Materials.lxm"\n\nInclude "LuxRender08_test_scene/Scene/00001/LuxRender-Geometry.lxo"\n\nInclude "LuxRender08_test_scene/Scene/00001/LuxRender-Volumes.lxv"\n\nAttributeBegin #  "Lamp"\n\nLightGroup "Sun"\n\nExterior  "clear-air"\n\nLightSource "sunsky"\n\t"float gain" [1.000000000000000]\n\t"float importance" [1.000000000000000]\n\t"float turbidity" [2.200000047683716]\n\t"integer nsamples" [4]\n\t"vector sundir" [-0.338262349367142 -0.562590241432190 0.754367828369141]\n\nAttributeEnd # ""\n\nExterior  "world"\nWorldEnd\n'

        import random
        random.seed(0)
        window = sfr.get_random_crop_window_for_verification(src)

        assert window == (0.24946508682591728, 0.39088644306322684,
                          0.7443999409582027, 0.8858212971955123)

        random.seed(0)
        window2 = sfr.get_random_crop_window_for_verification("")
        assert window2 == (0.3593384289059209, 0.9337946935597237,
                           0.32254274784931297, 0.8969990125031158)
