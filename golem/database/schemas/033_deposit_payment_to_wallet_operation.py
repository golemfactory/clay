# pylint: disable=no-member,unused-argument
import logging

SCHEMA_VERSION = 33

logger = logging.getLogger('golem.database')


STATUS_MAPPING = {
    1: 'awaiting',
    2: 'sent',
    3: 'confirmed',
    4: 'overdue',
}


def migrate_dp(database, db_row):
    status = STATUS_MAPPING[db_row['status']]
    database.execute_sql(
        "INSERT INTO walletoperation"
        " (tx_hash, direction, operation_type, status, sender_address,"
        "  recipient_address, amount, currency, gas_cost,"
        "  created_date, modified_date)"
        " VALUES (?, 'outgoing', 'deposit_payment', ?, '', '', ?, 'GNT', ?,"
        "        ?, datetime('now'))",
        (
            db_row['tx'],
            status,
            db_row['value'],
            db_row['fee'],
            db_row['created_date'],
        ),
    )


def migrate(migrator, database, fake=False, **kwargs):
    cursor = database.execute_sql(
        'SELECT tx, value, status, fee,'
        '       created_date'
        ' FROM depositpayment'
    )
    for db_row in cursor.fetchall():
        dict_row = {
            'tx': db_row[0],
            'value': db_row[1],
            'status': db_row[2],
            'fee': db_row[3],
            'created_date': db_row[4],
        }
        try:
            migrate_dp(database, dict_row)
        except Exception:  # pylint: disable=broad-except
            logger.error("Migration problem. db_row=%s", db_row, exc_info=True)


def rollback(migrator, database, fake=False, **kwargs):
    pass
