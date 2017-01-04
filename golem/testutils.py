import logging
import os
import shutil
import tempfile
import unittest
from os import path

from mock import MagicMock

from golem.core.common import is_windows, is_osx

from golem.core.simpleenv import get_local_datadir
from golem.model import Database
from golem.ethereum import Client


class TempDirFixture(unittest.TestCase):
    __root_dir = None

    @classmethod
    def setUpClass(cls):
        logging.basicConfig(level=logging.DEBUG)

        if is_windows():
            import win32api
            tmppath = win32api.GetLongPathName(tempfile.gettempdir())
        elif is_osx():
            tmppath = get_local_datadir('.tests')
        else:
            tmppath = tempfile.gettempdir()

        cls.__root_dir = path.join(tmppath, 'golem')
        if not os.path.exists(cls.__root_dir):
            os.makedirs(cls.__root_dir, mode=0770)

    # Concurrent tests will fail
    # @classmethod
    # def tearDownClass(cls):
    #     if os.path.exists(cls.__root_dir):
    #         shutil.rmtree(cls.__root_dir)

    def setUp(self):
        dir_name = self._temp_dir_name()
        self.tempdir = tempfile.mkdtemp(prefix=dir_name, dir=self.__root_dir)
        self.path = self.tempdir  # Alias for legacy tests
        if not is_windows():
            os.chmod(self.tempdir, 0770)

    def tearDown(self):
        # Firstly kill Ethereum node to clean up after it later on.
        # FIXME: This is temporary solution. Ethereum node should always be
        #        the explicit dependency and users should close it correctly.
        Client._kill_node()
        if path.isdir(self.tempdir):
            shutil.rmtree(self.tempdir)

    def temp_file_name(self, name):
        return path.join(self.tempdir, name)

    def additional_dir_content(self, file_num_list, dir_=None, results=None, sub_dir=None):
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
        if sub_dir:
            dir_ = os.path.join(dir_, sub_dir)
            if not os.path.exists(dir_):
                os.makedirs(dir_)
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

    def _temp_dir_name(self):
        return self.id().rsplit('.', 1)[1]  # Use test method name


class DatabaseFixture(TempDirFixture):
    """ Setups temporary database for tests."""

    def setUp(self):
        super(DatabaseFixture, self).setUp()
        self.database = Database(self.tempdir)

    def tearDown(self):
        self.database.db.close()
        super(DatabaseFixture, self).tearDown()


class TestGui(TempDirFixture):

    def setUp(self):
        super(TestGui, self).setUp()
        from gui.application import GNRGui
        from gui.view.appmainwindow import AppMainWindow

        self.logic = MagicMock()
        self.gnrgui = GNRGui(self.logic, AppMainWindow)

    def tearDown(self):
        super(TestGui, self).tearDown()
        self.gnrgui.app.exit(0)
        self.gnrgui.app.deleteLater()

