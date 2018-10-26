# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
SCHEMA_VERSION = 22


def _fix_payer_address(database):
    database.execute_sql(
        "UPDATE income "
        "SET payer_address = '0x' || payer_address "
        "WHERE payer_address NOT LIKE '0x%'",
    )


def migrate(migrator, database, fake=False, **kwargs):
    migrator.python(_fix_payer_address, database)


def rollback(migrator, database, fake=False, **kwargs):
    pass
