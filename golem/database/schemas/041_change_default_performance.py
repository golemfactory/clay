# pylint: disable=no-member
# pylint: disable=unused-argument
from golem.model import Performance
import peewee as pw

SCHEMA_VERSION = 41


def migrate(migrator, database, fake=False, **kwargs):
    database.truncate_table(Performance)
    migrator.remove_fields('performance', 'cpu_usage')
    migrator.add_fields('performance', cpu_usage=pw.IntegerField(
        default=Performance.DEFAULT_CPU_USAGE))


def rollback(migrator, database, fake=False, **kwargs):
    database.truncate_table(Performance)
    migrator.remove_fields('performance', 'cpu_usage')
    migrator.add_fields('performance', cpu_usage=pw.IntegerField(default=0))
