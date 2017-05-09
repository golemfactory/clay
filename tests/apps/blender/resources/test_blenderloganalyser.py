import os
from unittest import TestCase

import apps.blender.resources.blenderloganalyser as bla

LOG_FILE = "stdout.log_for_test"


class TestBlenderLogAnalyser(TestCase):
    @classmethod
    def _get_log_file(cls):
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                LOG_FILE)
        with open(log_path, 'r') as f:
            log_file = f.read()
        return log_file

    def test_find_missing_files(self):
        missing_files = bla.find_missing_files(self._get_log_file())
        assert "VSE_copy_proxy_path_to_all_strips.py" in missing_files
        assert "subsurf_change_level.py" in missing_files
        assert "set_ray_visibilities_for_selected_objects.py" in missing_files

    def test_find_rendering_time(self):
        time_rendering = bla.find_rendering_time(self._get_log_file())
        assert time_rendering == 11.82

        time_rendering = bla.find_rendering_time("No time in this log")
        assert time_rendering is None

    def test_find_output_file(self):
        output_file = bla.find_output_file(self._get_log_file())
        assert output_file == "/golem/output/kitty_10001.png"

        output_file = bla.find_output_file("No time in this log")
        assert output_file is None

    def test_find_resoultion(self):
        resolution = bla.find_resolution(self._get_log_file())
        assert resolution == (501, 230)

        resolution = bla.find_resolution("No resolution in this log")
        assert resolution is None

    def test_find_frames(self):
        frames = bla.find_frames(self._get_log_file())
        assert frames == range(0, 101)

        frames = bla.find_frames("No frames here")
        assert frames is None

        frames = bla.find_frames("Info: Frames: 24-113;10")
        assert frames == [24, 34, 44, 54, 64, 74, 84, 94, 104]

    def test_find_file_format(self):
        file_format = bla.find_file_format(self._get_log_file())
        assert file_format == ".png"

        file_format = bla.find_file_format("No file format here")
        assert file_format is None

    def test_filepath(self):
        filepath = bla.find_filepath(self._get_log_file())
        assert filepath == "/tmp/"

        filepath = bla.find_filepath("No filepath here")
        assert filepath is None
