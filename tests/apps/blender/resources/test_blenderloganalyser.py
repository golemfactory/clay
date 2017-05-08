from unittest import TestCase

from apps.blender.resources.blenderloganalyser import (find_missing_files, find_output_file,
                                                       find_rendering_time)

LOG_FILE = "stdout.log"


class TestBlenderLogAnalyser(TestCase):
    def _get_log_file(self):
        with open(LOG_FILE, 'r') as f:
            log_file = f.read()
        return log_file

    def test_find_missing_files(self):
        missing_files = find_missing_files(self._get_log_file())
        assert "VSE_copy_proxy_path_to_all_strips.py" in missing_files
        assert "subsurf_change_level.py" in missing_files
        assert "set_ray_visibilities_for_selected_objects.py" in missing_files

    def test_find_rendering_time(self):
        time_rendering = find_rendering_time(self._get_log_file())
        assert time_rendering == 15.57

        time_rendering = find_rendering_time("No time in this log")
        assert time_rendering is None

    def test_find_output_file(self):
        output_file = find_output_file(self._get_log_file())
        assert output_file == "/golem/output/kitty_10001.png"

        output_file = find_output_file("No time in this log")
        assert output_file is None

