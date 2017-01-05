from unittest import TestCase
from golem.ranking.manager import database_manager as dm
from golem.testutils import DatabaseFixture


class TestDatabaseManager(DatabaseFixture):
    def test_increase_positive_computed(self):
        dm.increase_positive_computed("alpha", 0.5)
        dm.increase_positive_computed("alpha", 0.7)
        assert dm.get_local_rank("alpha").positive_computed == 1.2
