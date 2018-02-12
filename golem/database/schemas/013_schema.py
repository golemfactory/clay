# pylint: disable=no-member
import peewee as pw

from golem.model import PaymentStatus


SCHEMA_VERSION = 13


def migrate(migrator, _database, **_kwargs):
    """Write your migrations here."""

    migrator.change_fields('networkmessage',
                           local_role=pw.ActorField(),
                           remote_role=pw.ActorField())

    migrator.change_fields('payment', status=pw.PaymentStatusField(
        default=PaymentStatus.awaiting, index=True
    ))


def rollback(migrator, _database, **_kwargs):
    """Write your rollback migrations here."""

    migrator.change_fields('payment', status=pw.EnumField(
        default=PaymentStatus.awaiting, index=True
    ))

    migrator.change_fields('networkmessage',
                           local_role=pw.EnumField(),
                           remote_role=pw.EnumField())
