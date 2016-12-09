import re

from golem.tools.testdirfixture import TestDirFixture
from apps.lux.resources.scenefileeditor import regenerate_lux_file


class TestSceneFileEditor(TestDirFixture):
    
    def testRegenerateLuxFile(self):
        scene_file_src = 'Film "fleximage"\n "bool write_exr" ["true"]\n "integer xresolution" [200] "integer yresolution" [100]\n "integer writeinterval" [15]\n "float cropwindow" [0, 1, 0, 1]'
        xres = 100
        yres = 200
        halttime = 0
        haltspp = 1
        writeinterval = 10
        crop = [0., 0.5, 0., 0.6]
        output_format = "PNG"
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, output_format)
        self.assertTrue('"bool write_resume_flm" ["true"]' in out)
        self.assertTrue('"integer xresolution" [' + str(xres) + ']' in out)
        self.assertTrue('"integer yresolution" [' + str(yres) + ']' in out)
        self.assertTrue('"integer halttime" [' + str(halttime) + ']' in out)
        self.assertTrue('"integer haltspp" [' + str(haltspp) + ']' in out)
        self.assertTrue('"integer writeinterval" [' + str(writeinterval) + ']' in out)
        self.assertTrue('"float cropwindow" [' + str(crop[0]) + ' ' + str(crop[1]) + ' ' + str(crop[2]) + ' ' + str(crop[3]) + ']' in out)
        scene_file_src2 = 'Film "fleximage"\n "bool write_resume_flm" ["true"]\n "integer xresolution" [200] "integer yresolution" [100]\n "integer writeinterval" [15]\n "float cropwindow" [0, 1, 0, 1]'

        out = regenerate_lux_file(scene_file_src2, xres, yres, halttime, haltspp, writeinterval, crop, "bla")
        self.assertEqual(len(re.findall("bool write_resume_flm", out)), 1)
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "png")
        assert len(re.findall('"bool write_png" \["true"\]', out)) == 1
        assert len(re.findall('"bool write_exr" \["false"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "PNG")
        assert len(re.findall('"bool write_png" \["true"\]', out)) == 1
        assert len(re.findall('"bool write_exr" \["false"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "exr")
        assert len(re.findall('"bool write_exr" \["true"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "EXR")
        assert len(re.findall('"bool write_exr" \["true"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "tga")
        assert len(re.findall('"bool write_tga" \["true"\]', out)) == 1
        assert len(re.findall('"bool write_exr" \["false"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src, xres, yres, halttime, haltspp, writeinterval, crop, "TGA")
        assert len(re.findall('"bool write_tga" \["true"\]', out)) == 1
        assert len(re.findall('"bool write_exr" \["false"\]', out)) == 1
        out = regenerate_lux_file(scene_file_src2, xres, yres, halttime, haltspp, writeinterval, crop, "exr")
        assert len(re.findall('"bool write_exr" \["true"\]', out)) == 1
