# pylint: disable=no-member
# pylint: disable=unused-argument
from golem import model

SCHEMA_VERSION = 20


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income',
        value_received=model.HexIntegerField(default=0),
    )
    migrator.sql(
        'UPDATE income SET value_received = value'
        ' WHERE "transaction" IS NOT NULL',
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'value_received')
