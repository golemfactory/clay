# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 44


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'requestedtask',
        min_memory=pw.IntegerField(default=0))
    migrator.change_fields(
        'requestedtask',
        max_price_per_hour=pw.HexIntegerField())
    migrator.change_fields(
        'requestedsubtask',
        price=pw.HexIntegerField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.change_fields(
        'requestedsubtask',
        payload=pw.JsonField(default='{}'),
        price=pw.IntegerField(null=True),
        inputs=pw.JsonField(default='[]'))
    migrator.change_fields(
        'requestedtask',
        app_params=pw.JsonField(default='{}'),
        max_price_per_hour=pw.IntegerField(),
        prerequisites=pw.JsonField(default='{}'))
    migrator.remove_fields(
        'requestedtask',
        'min_memory')
