# -*- coding: utf-8 -*-

import unittest
from unittest import TestCase
import os

from golem.testutils import TempDirFixture
from golem.core.mptee import MPTee
import subprocess

class TestTee(TempDirFixture, unittest.TestCase):
    def test_fileexists(self):
        logsfile = os.path.join(self.path, "testlog.log")
        print("logsfile: {}".format(logsfile))

        ps = subprocess.Popen(['sleep 1'], stdout=subprocess.PIPE, shell=True)
        mpt = MPTee(ps, logsfile)
        mpt.start()
        ps.wait()
        self.assertTrue(os.path.exists(logsfile))
        mpt.join()
