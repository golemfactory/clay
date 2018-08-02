# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
SCHEMA_VERSION = 18


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_not_null('income', 'payer_address')
    migrator.remove_index('income', 'sender_node', 'subtask')
    migrator.remove_fields('income', 'sender_node')
    migrator.add_index('income', 'payer_address', 'subtask')


def rollback(migrator, database, fake=False, **kwargs):
    migrator.drop_not_null('income', 'payer_address')
