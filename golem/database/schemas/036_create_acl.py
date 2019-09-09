# pylint: disable=no-member
# pylint: disable=unused-argument
import datetime as dt
import peewee as pw

SCHEMA_VERSION = 36


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model
    class ACLAllowedNodes(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        node_name = pw.CharField(max_length=255)

        class Meta:
            db_table = "aclallowednodes"

    @migrator.create_model
    class ACLDeniedNodes(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        node_name = pw.CharField(max_length=255)

        class Meta:
            db_table = "acldeniednodes"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model('acldeniednodes')
    migrator.remove_model('aclallowednodes')
