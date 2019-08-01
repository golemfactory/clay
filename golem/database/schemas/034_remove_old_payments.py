# pylint: disable=no-member,unused-argument
import datetime
import logging

import peewee as pw

SCHEMA_VERSION = 34

logger = logging.getLogger('golem.database')


def migrate(migrator, database, fake=False, **kwargs):
    migrator.remove_model('payment')


def rollback(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class Payment(pw.Model):
        subtask = pw.CharField()
        status = pw.IntegerField()
        payee = pw.RawCharField()
        value = pw.CharField()
        details = pw.RawCharField()
        processed_ts = pw.IntegerField(null=True)
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "payment"
