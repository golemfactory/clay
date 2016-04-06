from golem.model import Database
from golem.tools.testdirfixture import TestDirFixture


class TestWithDatabase(TestDirFixture):

    def setUp(self):
        super(TestWithDatabase, self).setUp()
        self.database = Database(self.path)

    def tearDown(self):
        self.database.db.close()
        super(TestWithDatabase, self).tearDown()
