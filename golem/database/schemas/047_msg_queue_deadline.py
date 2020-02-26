# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 47


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields('queuedmessage', deadline=pw.UTCDateTimeField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('queuedmessage', 'deadline')
