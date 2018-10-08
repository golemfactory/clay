# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 16


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields('income', settled_ts=pw.IntegerField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'settled_ts')
