from peewee import SqliteDatabase
from playhouse.shortcuts import RetryOperationalError


class GolemSqliteDatabase(RetryOperationalError, SqliteDatabase):

    def sequence_exists(self, seq):
        raise NotImplementedError()
