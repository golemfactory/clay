# pylint: disable=no-member
# pylint: disable=unused-argument
SCHEMA_VERSION = 19


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_not_null('income', 'payer_address')


def rollback(migrator, database, fake=False, **kwargs):
    migrator.drop_not_null('income', 'payer_address')
