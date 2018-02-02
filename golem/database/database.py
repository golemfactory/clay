import logging

from os import path
from peewee import SqliteDatabase
from playhouse.shortcuts import RetryOperationalError

from golem.database.migration.migrate import migrate_schema

log = logging.getLogger('golem.db')


class GolemSqliteDatabase(RetryOperationalError, SqliteDatabase):

    def sequence_exists(self, seq):
        raise NotImplementedError()


class Database:

    SCHEMA_VERSION = 10

    def __init__(self, db, datadir, models, migrate=True):
        self.db = db
        self.models = models
        self.db.init(path.join(datadir, 'golem.db'))
        self.db.connect()

        version = self.get_user_version()

        if not version:
            self._create_database()
        elif migrate and version < self.SCHEMA_VERSION:
            self._migrate_database(version, to_version=self.SCHEMA_VERSION)

    def close(self):
        if not self.db.is_closed():
            self.db.close()

    def get_user_version(self) -> int:
        cursor = self.db.execute_sql('PRAGMA user_version').fetchone()
        return int(cursor[0])

    def set_user_version(self, version: int) -> None:
        self.db.execute_sql('PRAGMA user_version = {}'.format(version))

    def _create_database(self) -> None:
        log.info("Creating database, version %r", self.SCHEMA_VERSION)

        self.db.create_tables(self.models, safe=True)
        self.set_user_version(self.SCHEMA_VERSION)

    def _migrate_database(self, version, to_version) -> None:
        log.info("Migrating database from version %r to %r",
                 version, to_version)

        migrate_schema(self, version, to_version)
