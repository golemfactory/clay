# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 41


def migrate(migrator, database, fake=False, **kwargs):
    migrator.change_fields(
        'requestedtask',
        max_price_per_hour=pw.HexIntegerField())
    migrator.change_fields(
        'requestedsubtask',
        price=pw.HexIntegerField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.change_fields(
        'requestedsubtask',
        payload=pw.JsonField(default='{}'))
    migrator.change_fields(
        'requestedtask',
        max_price_per_hour=pw.IntegerField())
