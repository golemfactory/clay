# pylint: disable=no-member
# pylint: disable=unused-argument
import datetime

import peewee as pw

SCHEMA_VERSION = 25


def migrate(migrator, database, fake=False, **kwargs):
    @migrator.create_model  # pylint: disable=unused-variable
    class CachedNode(pw.Model):
        node = pw.CharField(unique=True)
        node_field = pw.NodeField()
        created_date = pw.DateTimeField(default=datetime.datetime.now)
        modified_date = pw.DateTimeField(default=datetime.datetime.now)

        class Meta:
            db_table = "cachednode"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model("cachednode")
