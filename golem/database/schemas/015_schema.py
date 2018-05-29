# pylint: disable=no-member
# pylint: disable=too-few-public-methods
import peewee as pw

SCHEMA_VERSION = 15


def migrate(migrator, *_, **__):
    migrator.add_fields('performance',
                        min_accepted_step=pw.FloatField(default=300.0))


def rollback(migrator, *_, **__):
    migrator.remove_fields('performance', 'min_accepted_step')
