import unittest
import os

from golem.model import Database


class TestWithDatabase(unittest.TestCase):
    def setUp(self):
        if os.path.isfile('golem.db'):
            os.remove('golem.db')
        self.database = Database()

    def tearDown(self):
        self.database.db.close()
        if os.path.isfile('golem.db'):
            os.remove('golem.db')