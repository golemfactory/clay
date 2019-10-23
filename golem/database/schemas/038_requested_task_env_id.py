# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import peewee as pw

SCHEMA_VERSION = 38


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'requestedtask',
        env_id=pw.CharField(max_length=255, null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('requestedtask', 'env_id')
