# pylint: disable=no-member
# pylint: disable=too-few-public-methods
import peewee as pw
from golem.model import Income

SCHEMA_VERSION = 15


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income', origin=pw.StringEnumField(default=Income.Origin.node.value)
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'origin')
