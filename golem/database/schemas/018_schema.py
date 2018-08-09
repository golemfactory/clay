# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
import peewee as pw
from golem.model import Income
from golem.utils import pubkeytoaddr

SCHEMA_VERSION = 18


def _fill_payer_address():
    while True:
        entries = \
            Income.select().where(Income.payer_address.is_null()).limit(50)
        if not entries:
            break
        for entry in entries:
            entry.payer_address = pubkeytoaddr(entry.sender_node)[2:]
            entry.save()


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'income',
        payer_address=pw.CharField(max_length=255, null=True),
    )
    migrator.python(_fill_payer_address)


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('income', 'payer_address')
