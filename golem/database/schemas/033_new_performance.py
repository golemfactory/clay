# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime as dt
import peewee as pw

SCHEMA_VERSION = 33


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields('knownhosts', performance=pw.JsonField(default='{}'))

    @migrator.create_model
    class EnvironmentPerformance(pw.Model):
        environment = pw.CharField(max_length=255, primary_key=True)
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        performance = pw.FloatField()

        class Meta:
            db_table = "environmentperformance"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('knownhosts', 'performance')
    migrator.remove_model('environmentperformance')
