# pylint: disable=no-member,unused-argument
import json
import logging

SCHEMA_VERSION = 31

logger = logging.getLogger('golem.database')


STATUS_MAPPING = {
    1: 'awaiting',
    2: 'sent',
    3: 'confirmed',
    4: 'overdue',
}


def migrate_payment(database, db_row):
    details = json.loads(db_row['details'])
    status = STATUS_MAPPING[db_row['status']]
    cursor = database.execute_sql(
        "INSERT INTO walletoperation"
        " (tx_hash, direction, operation_type, status, sender_address,"
        "  recipient_address, amount, currency, gas_cost,"
        "  created_date, modified_date)"
        " VALUES (?, 'outgoing', 'task_payment', ?, '', ?, ?, 'GNT', ?,"
        "        ?, datetime('now'))",
        (
            f"0x{details['tx']}",
            status,
            f'0x{db_row["payee"]}',
            db_row['value'],
            details['fee'],
            db_row['created_date'],
        ),
    )
    wallet_operation_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO taskpayment"
        " (wallet_operation_id, node, task, subtask,"
        "  expected_amount, created_date, modified_date,"
        "  accepted_ts, settled_ts)"
        " VALUES (?, ?, '', ?, ?, ?, datetime('now'),"
        "         ?, ?)",
        (
            wallet_operation_id,
            details['node_info']['key'],
            db_row['subtask'],
            db_row['value'],
            db_row['created_date'],
        ),
    )


def migrate(migrator, database, fake=False, **kwargs):
    cursor = database.execute_sql(
        'SELECT details, status, payee, value, subtask, created_date'
        ' FROM payment'
    )
    for db_row in cursor.fetchall():
        dict_row = {
            'details': db_row[0],
            'status': db_row[1],
            'payee': db_row[2],
            'value': db_row[3],
            'subtask': db_row[4],
            'created_date': db_row[5],
        }
        try:
            migrate_payment(database, dict_row)
        except Exception:  # pylint: disable=broad-except
            logger.error("Migration problem. db_row=%s", db_row, exc_info=True)


def rollback(migrator, database, fake=False, **kwargs):
    pass
