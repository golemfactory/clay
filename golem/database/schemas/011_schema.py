# pylint: disable=no-member
import peewee as pw


SCHEMA_VERSION = 11


def migrate(migrator, _database, **_kwargs):
    """Write your migrations here."""

    migrator.remove_fields('expectedincome', 'sender_node_details')


def rollback(migrator, _database, **_kwargs):
    """Write your rollback migrations here."""

    migrator.add_fields('expectedincome', sender_node_details=pw.NodeField())
