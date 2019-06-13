import datetime
import logging
import os
import time
from typing import Optional, Type, Sequence

import peewee

from golem.database.migration import default_migrate_dir
from golem.database.migration.migrate import migrate_schema, MigrationError

logger = logging.getLogger('golem.db')


class GolemSqliteDatabase(peewee.SqliteDatabase):
    RETRY_TIMEOUT = datetime.timedelta(minutes=1)

    def sequence_exists(self, seq):
        raise NotImplementedError()

    def execute_sql(self, sql, params=None, require_commit=True):
        # Loosely based on
        # https://github.com/coleifer/peewee/blob/2.10.2/playhouse/shortcuts.py#L206-L219
        deadline = datetime.datetime.now() + self.RETRY_TIMEOUT
        iterations = 0
        while True:
            iterations += 1
            try:
                return super().execute_sql(sql, params, require_commit)
            except peewee.OperationalError as e:
                # Ignore transaction rollbacks
                if str(e).startswith('no such savepoint'):
                    logger.warning('execute_sql() tx rollback failed: %r', e)
                    return
                # Check retry deadline
                elif datetime.datetime.now() > deadline:
                    logger.warning(
                        "execute_sql() retry timeout after %d iterations."
                        " Giving up.",
                        iterations,
                    )
                    raise
                logger.debug(
                    "execute_sql(%r, params=%r, require_commit=%r)"
                    " failed (%d) with: %r. Retrying...",
                    sql,
                    params,
                    require_commit,
                    iterations,
                    e,
                )
                if not self.is_closed():
                    self.close()
                time.sleep(0)


class Database:

    SCHEMA_VERSION = 26

    def __init__(self,  # noqa pylint: disable=too-many-arguments
                 db: peewee.Database,
                 fields: Sequence[Type[peewee.Field]],
                 models: Sequence[Type[peewee.Model]],
                 db_dir: str,
                 db_name: str = 'golem.db',
                 schemas_dir: Optional[str] = default_migrate_dir()) -> None:

        self.fields = fields
        self.models = models
        self.schemas_dir = schemas_dir

        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        self.db = db
        self.db.init(os.path.join(db_dir, db_name))
        self.db.connect()

        version = self.get_user_version()

        if not version:
            self._create_tables()
        elif schemas_dir and version < self.SCHEMA_VERSION:
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
            if not self.schemas_dir:
                raise MigrationError("Invalid schema directory")

            migrate_schema(self, version, to_version,
                           migrate_dir=self.schemas_dir)
        except MigrationError as exc:
            logger.warning("Cannot migrate database schema: %s", exc)
            self._drop_tables()
            self._create_tables()
