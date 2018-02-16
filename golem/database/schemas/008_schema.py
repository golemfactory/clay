# pylint: disable=no-member
import peewee as pw


SCHEMA_VERSION = 8


def migrate(migrator, _database, **_kwargs):
    """Write your migrations here."""

    migrator.add_fields('expectedincome',
                        accepted_ts=pw.IntegerField(null=True))


def rollback(migrator, _database, **_kwargs):
    """Write your rollback migrations here."""

    migrator.remove_fields('expectedincome', 'accepted_ts')
