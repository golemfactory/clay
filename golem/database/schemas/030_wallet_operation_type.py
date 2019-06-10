# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw

SCHEMA_VERSION = 30


def migrate(migrator, database, fake=False, **kwargs):
    migrator.drop_not_null('walletoperation', 'tx_hash')
    migrator.remove_fields('taskpayment', 'accepted_ts', 'settled_ts')
    migrator.add_fields(
        'taskpayment',
        accepted_ts=pw.IntegerField(null=True, index=True),
        settled_ts=pw.IntegerField(null=True),
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.add_not_null('walletoperation', 'tx_hash')
    migrator.remove_fields('taskpayment', 'accepted_ts', 'settled_ts')
    migrator.add_fields(
        'taskpayment',
        accepted_ts=pw.DateTimeField(),
        settled_ts=pw.DateTimeField(),
    )
