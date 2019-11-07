# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw
from golem.model import Performance

SCHEMA_VERSION = 41


def migrate(migrator, database, fake=False, **kwargs):
    database.truncate_table(Performance)
    migrator.change_columns(Performance, cpu_usage=pw.IntegerField(
        default=Performance.DEFAULT_CPU_USAGE))


def rollback(migrator, database, fake=False, **kwargs):
    database.truncate_table(Performance)
    migrator.change_columns(Performance, cpu_usage=pw.IntegerField(default=0))
