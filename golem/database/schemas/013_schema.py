# pylint: disable=no-member
import peewee as pw


SCHEMA_VERSION = 13


def migrate(migrator, _database, **_kwargs):
    """Write your migrations here."""

    migrator.change_fields('networkmessage',
                           local_role=pw.ActorField(),
                           remote_role=pw.ActorField())


def rollback(migrator, _database, **_kwargs):
    """Write your rollback migrations here."""

    migrator.change_fields('networkmessage',
                           local_role=pw.EnumField(),
                           remote_role=pw.EnumField())
