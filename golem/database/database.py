import logging
from os import path

from peewee import SqliteDatabase
from playhouse.shortcuts import RetryOperationalError

from golem.database.migration.migrate import migrate_schema, NoMigrationScripts

logger = logging.getLogger('golem.db')


class GolemSqliteDatabase(RetryOperationalError, SqliteDatabase):

    def sequence_exists(self, seq):
        raise NotImplementedError()


class Database:

    SCHEMA_VERSION = 13

    def __init__(self, db, datadir, models, migrate=True):
        self.db = db
        self.models = models
        self.db.init(path.join(datadir, 'golem.db'))
        self.db.connect()

        version = self.get_user_version()

        if not version:
            self._create_tables()
        elif migrate and version < self.SCHEMA_VERSION:
            self._migrate_schema(version, to_version=self.SCHEMA_VERSION)

    def close(self):
        if not self.db.is_closed():
            self.db.close()

    def get_user_version(self) -> int:
        cursor = self.db.execute_sql('PRAGMA user_version').fetchone()
        return int(cursor[0])

    def set_user_version(self, version: int) -> None:
        self.db.execute_sql('PRAGMA user_version = {}'.format(version))

    def _drop_tables(self):
        logger.info("Removing tables")
        self.db.drop_tables(self.models, safe=True)

    def _create_tables(self) -> None:
        logger.info("Creating tables, schema version %r", self.SCHEMA_VERSION)

        self.db.create_tables(self.models, safe=True)
        self.set_user_version(self.SCHEMA_VERSION)

    def _migrate_schema(self, version, to_version) -> None:
        logger.info("Migrating database schema from version %r to %r",
                    version, to_version)

        try:
            migrate_schema(self, version, to_version)
        except NoMigrationScripts as exc:
            logger.warning("Cannot migrate database schema: %s", exc)
            self._drop_tables()
            self._create_tables()
