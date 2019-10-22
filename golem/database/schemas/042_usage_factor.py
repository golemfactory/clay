# pylint: disable=no-member
import datetime as dt
import peewee as pw

SCHEMA_VERSION = 42


def migrate(migrator, database, fake=False, **kwargs):

    @migrator.create_model
    class UsageFactor(pw.Model):
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        provider_node = pw.ForeignKeyField(
            db_column='provider_node_id',
            rel_model=migrator.orm['computingnode'],
            related_name='usage_factor',
            to_field='node_id',
            unique=True
        )
        usage_factor = pw.FloatField(default=1.0)

        class Meta:
            db_table = "usagefactor"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model('usagefactor')
