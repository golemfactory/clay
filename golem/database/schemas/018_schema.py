# pylint: disable=no-member
# pylint: disable=unused-argument
import peewee as pw
from golem_messages.utils import pubkey_to_address

SCHEMA_VERSION = 18


def _fill_payer_address(database):
    while True:
        cursor = database.execute_sql(
            "SELECT sender_node, subtask"
            " FROM income"
            " WHERE payer_address IS NULL"
            " LIMIT 50"
        )
        entries = cursor.fetchall()
        if not entries:
            break
        for entry in entries:
            sender_node, subtask = entry
            payer_address = pubkey_to_address(sender_node)[2:]
            database.execute_sql(
                "UPDATE income SET payer_address = ?"
                " WHERE sender_node = ? AND subtask = ?",
                (
                    payer_address,
                    sender_node,
                    subtask,
                ),
            )


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income',
        payer_address=pw.CharField(max_length=255, null=True),
    )
    migrator.python(_fill_payer_address, database)


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'payer_address')
