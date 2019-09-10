# pylint: disable=no-member,unused-argument
import logging

SCHEMA_VERSION = 31

logger = logging.getLogger('golem.database')


def migrate_income(database, db_row):
    if int(db_row['value'], 16) - int(db_row['value_received'], 16) == 0:
        status = 'confirmed'
    elif db_row['overdue']:
        status = 'overdue'
    else:
        status = 'awaiting'
    cursor = database.execute_sql(
        "INSERT INTO walletoperation"
        " (tx_hash, direction, operation_type, status, sender_address,"
        "  recipient_address, amount, currency, gas_cost,"
        "  created_date, modified_date)"
        " VALUES (?, 'incoming', 'task_payment', ?, '', ?, ?, 'GNT', 0,"
        "        ?, datetime('now'))",
        (
            f"0x{db_row['transaction']}",
            status,
            f'0x{db_row["payer_address"]}',
            db_row['value_received'],
            db_row['created_date'],
        ),
    )
    wallet_operation_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO taskpayment"
        " (wallet_operation_id, node, task, subtask,"
        "  expected_amount, created_date, modified_date,"
        "  accepted_ts, settled_ts)"
        " VALUES (?, ?, '', ?, ?, ?, datetime('now'), "
        "         ?, ?)",
        (
            wallet_operation_id,
            f"0x{db_row['sender_node']}",
            db_row['subtask'],
            db_row['value'],
            db_row['created_date'],
            db_row['accepted_ts'],
            db_row['settled_ts'],
        ),
    )


def migrate(migrator, database, fake=False, **kwargs):
    if 'income' not in database.get_tables():
        logger.info('income table not in DB. Skipping this migration.')
        return

    cursor = database.execute_sql(
        'SELECT "transaction", payer_address, value, value_received, subtask,'
        '       created_date,'
        '       accepted_ts, settled_ts,'
        '       overdue, sender_node'
        ' FROM income'
    )

    for db_row in cursor.fetchall():
        dict_row = {
            'transaction': db_row[0],
            'payer_address': db_row[1],
            'value': db_row[2],
            'value_received': db_row[3],
            'subtask': db_row[4],
            'created_date': db_row[5],
            'accepted_ts': db_row[6],
            'settled_ts': db_row[7],
            'overdue': db_row[8],
            'sender_node': db_row[9],
        }
        try:
            migrate_income(database, dict_row)
        except Exception:  # pylint: disable=broad-except
            logger.error("Migration problem. db_row=%s", db_row, exc_info=True)


def rollback(migrator, database, fake=False, **kwargs):
    pass
