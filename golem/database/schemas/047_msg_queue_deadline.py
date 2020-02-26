# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

from golem.model import default_msg_deadline

SCHEMA_VERSION = 47


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'queuedmessage',
        deadline=pw.UTCDateTimeField(default=default_msg_deadline())
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('queuedmessage', 'deadline')
