from golem import model as m
from golem.database import Database
from golem.testutils import DatabaseFixture, PEP8MixIn


class TestDatabase(DatabaseFixture, PEP8MixIn):
    PEP8_FILES = ["golem/model.py", "golem/database/database.py"]

    def test_init(self):
        self.assertFalse(self.database.db.is_closed())

        for model in m.DB_MODELS:
            self.assertTrue(model.table_exists())

    def test_schema_version(self):
        self.assertEqual(self.database.get_user_version(),
                         self.database.SCHEMA_VERSION)
        self.assertNotEqual(self.database.SCHEMA_VERSION, 0)

        self.database.set_user_version(0)
        self.assertEqual(self.database.get_user_version(), 0)

        self.database.close()
        database = Database(m.db, fields=m.DB_FIELDS, models=m.DB_MODELS,
                            db_dir=self.path)
        self.assertEqual(database.get_user_version(), database.SCHEMA_VERSION)
        database.close()
