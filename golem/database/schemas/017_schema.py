# pylint: disable=no-member

import peewee as pw

SCHEMA_VERSION = 17


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'knownhosts',
        metadata=pw.JsonField(default='{}'))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('knownhosts', 'metadata')
