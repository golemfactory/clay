# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=too-few-public-methods
import datetime

import peewee as pw

SCHEMA_VERSION = 21


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class DepositPayment(pw.Model):
        dbid = pw.PrimaryKeyField()
        value = pw.CharField()
        status = pw.IntegerField()
        fee = pw.CharField()
        block_hash = pw.CharField(max_length=64)
        block_number = pw.CharField()
        tx = pw.CharField(max_length=64)
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "depositpayment"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("depositpayment")
