# pylint: disable=no-member
# pylint: disable=unused-variable
import datetime as dt
import peewee as pw


SCHEMA_VERSION = 12


def migrate(migrator, _database, **_kwargs):
    """Write your migrations here."""

    migrator.drop_index('hardwarepreset', 'name')

    migrator.add_index('hardwarepreset', 'name', unique=True)

    migrator.add_fields('income', accepted_ts=pw.IntegerField(null=True))

    migrator.change_fields('income', value=pw.HexIntegerField())

    migrator.drop_not_null('income', 'transaction')

    migrator.change_fields('payment', value=pw.HexIntegerField())

    migrator.drop_index('performance', 'environment_id')

    migrator.add_index('performance', 'environment_id', unique=True)

    migrator.remove_model('expectedincome')


def rollback(migrator, _database, **_kwargs):
    """Write your rollback migrations here."""

    migrator.drop_index('performance', 'environment_id')

    migrator.add_index('performance', 'environment_id', unique=True)

    migrator.change_fields('payment', value=pw.HexIntegerField())

    migrator.remove_fields('income', 'accepted_ts')

    migrator.change_fields('income', value=pw.HexIntegerField())

    migrator.add_not_null('income', 'transaction')

    migrator.drop_index('hardwarepreset', 'name')

    migrator.add_index('hardwarepreset', 'name', unique=True)

    @migrator.create_model
    class ExpectedIncome(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        sender_node = pw.CharField(max_length=255)
        subtask = pw.CharField(max_length=255)
        value = pw.HexIntegerField()
        accepted_ts = pw.IntegerField(null=True)

        class Meta:
            db_table = "expectedincome"
