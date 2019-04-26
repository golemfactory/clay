# pylint: disable=no-member
# pylint: disable=unused-argument
import datetime

import peewee as pw

SCHEMA_VERSION = 21


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class QueuedMessage(pw.Model):
        node = pw.CharField()
        msg_version = pw.CharField()
        msg_cls = pw.CharField()
        msg_data = pw.BlobField()
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "queuedmessage"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("queuedmessage")
