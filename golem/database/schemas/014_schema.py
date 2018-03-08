# pylint: disable=no-member
# pylint: disable=too-few-public-methods
import peewee as pw

SCHEMA_VERSION = 14


def migrate(migrator, *_, **__):
    migrator.add_fields(
        'income',
        overdue=pw.BooleanField(default=False))


def rollback(migrator, *_, **__):
    migrator.remove_fields('income', 'overdue')
