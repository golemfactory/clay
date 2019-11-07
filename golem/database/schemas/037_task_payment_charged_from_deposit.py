# pylint: disable=no-member
# pylint: disable=unused-argument
from golem import model

SCHEMA_VERSION = 37


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'taskpayment',
        charged_from_deposit=model.BooleanField(null=True),
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('taskpayment', 'charged_from_deposit')
