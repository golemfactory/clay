#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import shutil
import getpass

from golem.core.common import get_golem_path, is_windows
from golem.core.fileshelper import get_dir_size, common_dir, outer_dir_path, inner_dir_path, du
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
        assert outer_dir_path(path) == os.path.join('dir', 'file')
        assert outer_dir_path('file') == 'file'
        assert outer_dir_path('') == ''
        assert inner_dir_path(path, 'inner') == os.path.join('dir', 'subdir', 'inner', 'file')

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
