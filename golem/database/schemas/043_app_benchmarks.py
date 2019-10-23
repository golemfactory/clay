# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import datetime as dt
import peewee as pw

SCHEMA_VERSION = 43


def migrate(migrator, database, fake=False, **kwargs):

    @migrator.create_model
    class AppBenchmark(pw.Model):
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        hash = pw.CharField(max_length=255, unique=True)
        score = pw.FloatField()
        cpu_usage = pw.IntegerField(default=1)

        class Meta:
            db_table = "appbenchmark"


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model('appbenchmark')
