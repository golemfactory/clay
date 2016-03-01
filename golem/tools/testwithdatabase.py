import unittest
import os
import random

from golem.model import Database
from golem.tools.testdirfixture import TestDirFixture


class TestWithDatabase(TestDirFixture):

    def setUp(self):
        TestDirFixture.setUp(self)
        self.name = os.path.join(self.path, "golem" + str(random.randint(1, 1000)) + ".db")
        self.database = Database(self.name)

    def tearDown(self):
        self.database.db.close()
        TestDirFixture.tearDown(self)
