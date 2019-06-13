# pylint: disable=no-member
# pylint: disable=unused-argument
import datetime

import peewee as pw

SCHEMA_VERSION = 28


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class TaskPayment(pw.Model):
        wallet_operation_id = pw.IntegerField()
        node = pw.CharField()
        task = pw.CharField()
        subtask = pw.CharField()
        expected_amount = pw.CharField()
        accepted_ts = pw.DateTimeField()
        settled_ts = pw.DateTimeField()
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "taskpayment"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("taskpayment")
