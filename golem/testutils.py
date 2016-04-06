import logging
import shutil
import tempfile
import unittest
from os import path, mkdir


class TempDirFixture(unittest.TestCase):
    def setUp(self):
        logging.basicConfig(level=logging.DEBUG)
        root = path.join(tempfile.gettempdir(), 'golem')
        if not path.exists(root):
            mkdir(root)
        self.tempdir = tempfile.mkdtemp(prefix=self.id(), dir=root)
        self.path = self.tempdir  # Alias for legacy tests

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def temp_file_name(self, name):
        return path.join(self.tempdir, name)

    def additional_dir_content(self, file_num_list, dir_=None, results=None):
        """ Create recursively additional temporary files in directories in given directory
        For example file_num_list in format [5, [2], [4, []]] will create 5 files in self.tempdir directory,
        and 2 subdirectories - first one will contain 2 tempfiles, second will contain 4 tempfiles and
        an empty subdirectory
        :param file_num_list: list containing number of new files that should be created in this directory or
            list describing file_num_list for new inner directories
        :param dir_: directory in which files should be created
        :param results: list of created temporary files
        :return:
        """
        if dir_ is None:
            dir_ = self.tempdir
        if results is None:
            results = []
        for el in file_num_list:
            if isinstance(el, int):
                for i in range(el):
                    t = tempfile.NamedTemporaryFile(dir=dir_, delete=False)
                    results.append(t.name)
            else:
                new_dir = tempfile.mkdtemp(dir=dir_)
                self.additional_dir_content(el, new_dir, results)
        return results
