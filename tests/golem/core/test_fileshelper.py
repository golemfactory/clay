#!/usr/bin/env python
# -*- coding: utf-8 -*-

import getpass
import os
import re
import shutil

from golem.core.common import get_golem_path, is_windows
from golem.core.fileshelper import (common_dir, copy_file_tree, du, find_file_with_ext,
                                    get_dir_size, has_ext, inner_dir_path, outer_dir_path)
from golem.tools.testdirfixture import TestDirFixture


class TestDirSize(TestDirFixture):
    def setUp(self):
        TestDirFixture.setUp(self)
        self.testdir = self.path
        self.testfile1 = os.path.join(self.testdir, "testfile1")
        self.testdir2 = os.path.join(self.testdir, "testdir2")
        self.testfile2 = os.path.join(self.testdir2, "testfile2")
        self.testdir3 = os.path.join(self.testdir, "testdir3")
        self.testfile3 = os.path.join(self.testdir3, "testfile3")

    def test_dir_size(self):
        with self.assertRaises(OSError):
            get_dir_size("notexisting")

        with open(self.testfile1, 'w') as f:
            f.write("a" * 20000)
        os.makedirs(self.testdir2)
        with open(self.testfile2, 'w') as f:
            f.write("b" * 30000)
        size = get_dir_size(self.testdir)

        self.assertGreaterEqual(size, 50000)

        self.assertGreater(get_dir_size(get_golem_path()), 3 * 1024 * 1024)

        if not is_windows():
            os.makedirs(self.testdir3)
            with open(self.testfile3, 'w') as f:
                f.write("c" * 30000)
            os.chmod(self.testdir3, 0o200)
            new_size = get_dir_size(self.testdir)
            self.assertGreaterEqual(new_size, size)

            if getpass.getuser() != 'root':
                errors = []
                get_dir_size(self.testdir, report_error=errors.append)
                self.assertEqual(len(errors), 1)
                self.assertIs(type(errors[0]), OSError)

    def testOuterInnerDir(self):
        path = os.path.join('dir', 'subdir', 'file')
        self.assertEqual(outer_dir_path(path), os.path.join('dir', 'file'))
        self.assertEqual(outer_dir_path('file'), 'file')
        self.assertEqual(outer_dir_path(''), '')
        self.assertEqual(inner_dir_path(path, 'inner'), os.path.join('dir', 'subdir', 'inner', 'file'))

    def testCommonDir(self):
        paths = {
            'win': [
                (['C:/dir', "C:/"],  'C:'),
                (['C:/dir', "C:\\"], "C:"),
                (['C:/dir', 'C:\\'], "C:"),
                (['C:/',    "C:\\"], 'C:'),
                (['Ł:/dir', "Ł:\\"], "Ł:"),
                (['C:\\dirę', 'C:\\dirą', ], "C:"),
                ([
                    'C:/dir/file.txt',
                    "C:\\dir\\subdir\\file.txt",
                 ],
                 'C:/dir'),
                ([
                    'C:\\dir\\file.txt',
                    'C:\\dir/subdir/file.txt',
                 ],
                 "C:\\dir"),
                ([
                     'C:\\dir\\file.txt',
                     'C:/dir/subdir\\file.txt',
                 ],
                 "C:\\dir"),
                ([
                     'C:/dir\\file.txt',
                     'C:\\dir/subdir\file.txt',
                 ],
                 "C:/dir"),
                ([
                     'C:/dir/subdir/file.txt',
                     'C:\\dir/subdir-d\\subdir/file.txt',
                 ],
                 'C:/dir'),
                ([
                     'C:/dir/subdir-d/file.txt',
                     'C:\\dir/subdir\\subdir/file.txt',
                 ],
                 'C:/dir'),
                ([
                     'C:/dir/subdir',
                     'C:\\dir/subdir\\subdir/file.txt',
                 ],
                 'C:/dir/subdir'),
                ([
                     'C:/dir/Subdir',
                     'C:\\dir/subdir\\subdir/file.txt',
                 ],
                 'C:/dir/Subdir')
            ],
            'other': [
                (['/var/log/daemon.log'], ''),
                (['/', '/var'], ''),
                ([], ''),
                ([
                    '/var/log/daemon/daemon.log',
                    '/var/log/daemon.log',
                 ],
                 '/var/log'),
                ([
                    '/var/log-other/daemon/daemon.log',
                    '/var/log/daemon.log',
                 ],
                 '/var'),
                ([
                    u'/var/log-other/daemon/daemon.log',
                    '/var/log/daemon.log',
                 ],
                 '/var'),
                ([
                    u'/var/log-other/daemon/daemon.log',
                    u'/var/log/daemon.log',
                 ],
                 '/var'),
                ([
                    '/var/log-other/daemon/daemon.log',
                    '/var/log/daemon.log',
                    '/var/run/daemon.sock'
                 ],
                 '/var'),
                ([
                    '/vąr/log/daęmon/daemon.log',
                    '/vąr/log/daęmon/daęmon.log',
                    '/vąr/lóg/daęmon/daęmon.log'
                 ],
                 '/vąr'),
                ([
                    '/vąr/log/daęmon/daemon.log',
                    '/vąr/log/daęmon/daęmon.log'
                 ],
                 '/vąr/log/daęmon'),
                ([
                    '/vąr/log/daęmon',
                    '/vąr/log/daęmon/subdir/daęmon.log'
                 ],
                 '/vąr/log/daęmon'),
                ([
                    '/vąr/log/daęmon',
                    '/vąr/log/daęmon-d/subdir/daęmon.log'
                 ],
                 '/vąr/log'),
                ([
                    '/var/log/daemon/daemon.log',
                    '/var/log/daemon/file.log',
                    '/var/log/daemon/file3.log',
                    '/var/log/daemon/other/file.log',
                 ],
                 '/var/log/daemon'),
                ([
                    '/var/log/daemon',
                    '/var/log/daemon',
                    '/var/log/daemon',
                    '/var/log/daemon/other',
                 ],
                 '/var/log/daemon'),
                ([
                    '/var/log/daemon',
                    '/var/log/Daemon',
                    '/var/log/daemon'
                 ],
                 '/var/log'),
                ([
                     '/var/log/',
                     '/var/log/'
                 ],
                 '/var/log')
            ]
        }

        def check(key, ign_case):
            for t in paths[key]:
                r = common_dir(t[0], ign_case=ign_case)
                if r != t[1]:
                    self.fail("{} -> {} != {}".format(t[0], r, t[1]))

        check('win', ign_case=True)
        check('other', ign_case=False)

        self.assertEqual(common_dir(None), '')
        self.assertEqual(common_dir(['/var/log']), '')

    def tearDown(self):
        if not is_windows():
            if os.path.isdir(self.testdir3):
                os.chmod(self.testdir3, 0o700)
            if os.path.isfile(self.testfile3):
                os.chmod(self.testfile3, 0o600)

        if os.path.isdir(self.testdir):
            shutil.rmtree(self.testdir)


class TestDu(TestDirFixture):

    def test_du(self):
        files_ = self.additional_dir_content([1, [1]])
        testdir = self.path
        testdir2 = os.path.dirname(files_[1])
        testfile1 = files_[0]
        testfile2 = files_[1]
        res = du("notexisting")
        self.assertEqual(res, "-1")
        res = du(testdir)
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreaterEqual(float(size), 0.0)
        with open(os.path.join(testdir, testfile1), 'w') as f:
            f.write("a" * 10000)
        res = du(testdir)
        size1, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size1), float(size))
        if not os.path.exists(testdir2):
            os.makedirs(testdir2)
        with open(os.path.join(testdir2, testfile2), 'w') as f:
            f.write("123" * 10000)
        res = du(testdir)
        size2, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(float(size2), float(size1))
        res = du(".")
        try:
            size = float(res)
        except ValueError:
            size, sym = re.split("[ kKmMgGbB]", res)[:2]
        self.assertGreater(size, 0)


class TestFindAndCopy(TestDirFixture):
    """ Test finding files with extensions and coping file free"""

    def setUp(self):
        TestDirFixture.setUp(self)

        self.test_dir1 = os.path.join(self.path, "test_dir")
        self.test_dir2 = os.path.join(self.test_dir1, "test_dir")
        self.test_file_1 = os.path.join(self.test_dir1, "txt_file_1.txt")
        self.test_file_2 = os.path.join(self.test_dir1, "txt_file_2.txt")
        self.test_file_3 = os.path.join(self.test_dir1, "jpg_file_3.jpg")
        self.test_file_4 = os.path.join(self.test_dir2, "jpg_file_1.jpg")
        self.test_file_5 = os.path.join(self.test_dir2, "test_file_2.txt2")
        self.test_file_6 = os.path.join(self.test_dir2, "txt_file_3.txt")

        # create dirs
        os.makedirs(self.test_dir1, 0o777)
        os.makedirs(self.test_dir2, 0o777)

        # create files
        open(self.test_file_1, 'a').close()
        open(self.test_file_2, 'a').close()
        open(self.test_file_3, 'a').close()
        open(self.test_file_4, 'a').close()
        open(self.test_file_5, 'a').close()
        open(self.test_file_6, 'a').close()

    def tearDown(self):
        # clean up
        os.remove(self.test_file_1)
        os.remove(self.test_file_2)
        os.remove(self.test_file_3)
        os.remove(self.test_file_4)
        os.remove(self.test_file_5)
        os.remove(self.test_file_6)

        os.rmdir(self.test_dir2)
        os.rmdir(self.test_dir1)

    def test_find_file_with_ext(self):
        """ Test find_file_with_ext method """

        # try to find not existing file
        self.assertIsNone(find_file_with_ext(self.test_file_6, ['.avi']))
        # search recursively
        self.assertTrue(find_file_with_ext(self.test_dir1, ['.txt2']).endswith(".txt2"))
        # simple search
        self.assertTrue(find_file_with_ext(self.test_dir2, ['.txt']).endswith(".txt"))
        # search with multiple patterns
        file_ = find_file_with_ext(self.test_dir1, ['.txt', '.jpg'])
        self.assertTrue(file_.endswith(".txt") or file_.endswith(".jpg"))
        # search with multiple patterns (one is incorrect)
        self.assertTrue(find_file_with_ext(self.test_dir1, ['.txt', '.incorrect']).endswith(".txt"))

    def test_copy_file_tree(self):
        """ Test coping file tree without any excludes """
        copy_path = os.path.join(self.path, "copy_test_dir")
        copy_file_tree(self.test_dir1, copy_path)

        from filecmp import dircmp
        dcmp = dircmp(self.test_dir1, copy_path)
        self.assertEqual(dcmp.left_list, dcmp.right_list)

    def test_copy_file_tree_excludes(self):
        """ Test coping file tree with excludes """
        copy_path = os.path.join(self.path, "copy_test_dir")
        copy_file_tree(self.test_dir2, copy_path)

        from filecmp import dircmp
        dcmp = dircmp(self.test_dir2, copy_path, ignore=[os.path.basename(self.test_file_5)])
        self.assertEqual(dcmp.left_list, dcmp.right_list)


class TestHasExt(TestDirFixture):
    def test_has_ext(self):
        file_names = ["file.ext", "file.dde", "file.abc", "file.ABC", "file.Abc", "file.DDE",
                       "file.XYZ", "file.abC"]
        files = [self.temp_file_name(f) for f in file_names]
        for f in files:
            with open(f, 'w'):
                pass
        assert has_ext(file_names[0], ".ext")
        assert has_ext(file_names[0], ".EXT")
        assert not has_ext(file_names[0], ".EXT", True)
        assert has_ext(file_names[0], ".ext", True)
        assert not has_ext(file_names[0], ".exr")

        assert len(filter(lambda x: has_ext(x, ".abc"), file_names)) == 4
        assert len(filter(lambda x: has_ext(x, ".abc", True), file_names)) == 1

        assert has_ext(file_names[6], ".xyz")
        assert not has_ext(file_names[6], ".xyz", True)
