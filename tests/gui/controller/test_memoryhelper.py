from golem.tools.assertlogs import LogTestCase

from gui.controller.memoryhelper import dir_size_to_display, logger, resource_size_to_display, translate_resource_index


class TestMemoryHelper(LogTestCase):
    def test_translate_resource_index(self):
        with self.assertLogs(logger, level="ERROR"):
            assert translate_resource_index(3) == ""
        assert translate_resource_index(2) == 'GB'
        assert translate_resource_index(1) == 'MB'
        assert translate_resource_index(0) == 'kB'

    def test_resource_size_to_display(self):
        assert resource_size_to_display(1073741824) == (1024, 2)
        assert resource_size_to_display(1048576) == (1, 2)
        assert resource_size_to_display(1024) == (1, 1)
        assert resource_size_to_display(512) == (512, 0)

    def test_dir_size_to_display(self):
        assert dir_size_to_display(1073741824) == (1, 2)
        assert dir_size_to_display(1048576) == (1, 1)
        assert dir_size_to_display(1024) == (1, 0)
