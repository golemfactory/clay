# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 46


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'requestedtask',
        end_time=pw.UTCDateTimeField(null=True))


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('requestedtask', 'end_time')
