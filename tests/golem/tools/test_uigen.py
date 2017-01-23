from os import path, makedirs
from shutil import copyfile

from golem.tools.testdirfixture import TestDirFixture
from golem.tools.uigen import regenerate_ui_files
from golem.core.common import get_golem_path


class TestRegenerateUIFiles(TestDirFixture):
    def test_regenerate_cmd_called(self):
        makedirs(path.join(self.path, "gen"))
        test_ui_file_name = "NodeNameDialog.ui"
        test_ui_file = path.join(get_golem_path(), "gui", "view",  test_ui_file_name)
        tmp_ui_file = path.join(self.path, test_ui_file_name)
        copyfile(test_ui_file, tmp_ui_file)
        regenerate_ui_files(self.path)