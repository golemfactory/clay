# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 39


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields('performance', cpu_usage=pw.IntegerField(default=0))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('performance', 'cpu_usage')
