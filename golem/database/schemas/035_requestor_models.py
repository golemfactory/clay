# pylint: disable=no-member
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import datetime as dt
import peewee as pw

SCHEMA_VERSION = 35


def migrate(migrator, database, fake=False, **kwargs):

    @migrator.create_model
    class ComputingNode(pw.Model):
        node_id = pw.CharField(max_length=255, primary_key=True)
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        name = pw.CharField(max_length=255)

        class Meta:
            db_table = "computingnode"

    @migrator.create_model
    class RequestedTask(pw.Model):
        task_id = pw.CharField(max_length=255, primary_key=True)
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        app_id = pw.CharField(max_length=255)
        name = pw.CharField(max_length=255, null=True)
        status = pw.StringEnumField()
        environment = pw.CharField(max_length=255)
        prerequisites = pw.JsonField(default='{}')
        task_timeout = pw.IntegerField()
        subtask_timeout = pw.IntegerField()
        start_time = pw.UTCDateTimeField(null=True)
        max_price_per_hour = pw.IntegerField()
        max_subtasks = pw.IntegerField()
        concent_enabled = pw.BooleanField(default=False)
        prerequisites = pw.JsonField(default='[]')
        mask = pw.BlobField(
            default=b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
                    b'\x00\x00\x00\x00')
        output_directory = pw.CharField(max_length=255)
        app_params = pw.JsonField(default='{}')

        class Meta:
            db_table = "requestedtask"

    @migrator.create_model
    class RequestedSubtask(pw.Model):
        created_date = pw.UTCDateTimeField(default=dt.datetime.now)
        modified_date = pw.UTCDateTimeField(default=dt.datetime.now)
        task = pw.ForeignKeyField(
            db_column='task_id',
            rel_model=migrator.orm['requestedtask'],
            related_name='subtasks',
            to_field='task_id')
        subtask_id = pw.CharField(max_length=255)
        status = pw.StringEnumField()
        payload = pw.JsonField(default='{}')
        inputs = pw.JsonField(default='[]')
        start_time = pw.UTCDateTimeField(null=True)
        price = pw.IntegerField(null=True)
        computing_node = pw.ForeignKeyField(
            db_column='computing_node_id',
            null=True,
            rel_model=migrator.orm['computingnode'],
            related_name='subtasks',
            to_field='node_id')

        class Meta:
            db_table = "requestedsubtask"
            primary_key = pw.CompositeKey('task', 'subtask_id')


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_model('requestedsubtask')
    migrator.remove_model('requestedtask')
    migrator.remove_model('computingnode')
