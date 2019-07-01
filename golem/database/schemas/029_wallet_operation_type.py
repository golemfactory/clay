# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 29


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'walletoperation',
        operation_type=pw.CharField(default='task_payment'),
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('walletoperation', 'task_payment')
