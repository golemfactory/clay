# pylint: disable=no-member,unused-argument
import datetime
import logging

import peewee as pw

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
        " VALUES (?, 'outgoing', 'deposit_transfer', ?, '', '', ?, 'GNT', ?,"
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
    if 'depositpayment' not in database.get_tables():
        logger.info('depositpayment table not in DB. Skipping this migration.')
        return

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

    migrator.remove_model('depositpayment')


def rollback(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class DepositPayment(pw.Model):
        value = pw.CharField()
        status = pw.IntegerField()
        fee = pw.CharField(null=True)
        tx = pw.CharField(max_length=66, primary_key=True)
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "depositpayment"
