# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
import peewee as pw
from golem.model import IncomeOrigin

SCHEMA_VERSION = 16


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income', origin=pw.IncomeOriginField(default=IncomeOrigin.node))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'origin')
