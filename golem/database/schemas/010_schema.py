SCHEMA_VERSION = 10
from golem.model import *  # pylint: disable=unused-import

"""Peewee migrations -- 010_schema.py.

Some examples (model - class or model name)::

    > Model = migrator.orm['model_name']            # Return model in current state by name

    > migrator.sql(sql)                             # Run custom SQL
    > migrator.python(func, *args, **kwargs)        # Run python code
    > migrator.create_model(Model)                  # Create a model (could be used as decorator)
    > migrator.remove_model(model, cascade=True)    # Remove a model
    > migrator.add_fields(model, **fields)          # Add fields to a model
    > migrator.change_fields(model, **fields)       # Change fields
    > migrator.remove_fields(model, *field_names, cascade=True)
    > migrator.rename_field(model, old_field_name, new_field_name)
    > migrator.rename_table(model, new_table_name)
    > migrator.add_index(model, *col_names, unique=False)
    > migrator.drop_index(model, *col_names)
    > migrator.add_not_null(model, *field_names)
    > migrator.drop_not_null(model, *field_names)
    > migrator.add_default(model, field_name, default)

"""

import datetime as dt
import peewee as pw

try:
    import playhouse.postgres_ext as pw_pext
except ImportError:
    pass


def migrate(migrator, database, fake=False, **kwargs):
    """Write your migrations here."""

    @migrator.create_model
    class Account(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)

        class Meta:
            db_table = "account"

    @migrator.create_model
    class BaseModel(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)

        class Meta:
            db_table = "basemodel"

    @migrator.create_model
    class ExpectedIncome(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        sender_node = pw.CharField(max_length=255)
        sender_node_details = pw.NodeField()
        subtask = pw.CharField(max_length=255)
        value = pw.BigIntegerField()
        accepted_ts = pw.IntegerField(null=True)

        class Meta:
            db_table = "expectedincome"

    @migrator.create_model
    class GenericKeyValue(pw.Model):
        key = pw.CharField(max_length=255, primary_key=True)
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        value = pw.CharField(max_length=255, null=True)

        class Meta:
            db_table = "generickeyvalue"

    @migrator.create_model
    class GlobalRank(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        requesting_trust_value = pw.FloatField(default=0.0)
        computing_trust_value = pw.FloatField(default=0.0)
        gossip_weight_computing = pw.FloatField(default=0.0)
        gossip_weight_requesting = pw.FloatField(default=0.0)

        class Meta:
            db_table = "globalrank"

    @migrator.create_model
    class HardwarePreset(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        name = pw.CharField(max_length=255, unique=True)
        cpu_cores = pw.SmallIntegerField()
        memory = pw.IntegerField()
        disk = pw.IntegerField()

        class Meta:
            db_table = "hardwarepreset"

    @migrator.create_model
    class Income(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        sender_node = pw.CharField(max_length=255)
        subtask = pw.CharField(max_length=255)
        transaction = pw.CharField(max_length=255)
        value = pw.BigIntegerField()

        class Meta:
            db_table = "income"

            primary_key = pw.CompositeKey('sender_node', 'subtask')

    @migrator.create_model
    class KnownHosts(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        ip_address = pw.CharField(max_length=255)
        port = pw.IntegerField()
        last_connected = pw.DateTimeField(default=dt.datetime.now)
        is_seed = pw.BooleanField(default=False)

        class Meta:
            db_table = "knownhosts"

    @migrator.create_model
    class LocalRank(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255, unique=True)
        positive_computed = pw.FloatField(default=0.0)
        negative_computed = pw.FloatField(default=0.0)
        wrong_computed = pw.FloatField(default=0.0)
        positive_requested = pw.FloatField(default=0.0)
        negative_requested = pw.FloatField(default=0.0)
        positive_payment = pw.FloatField(default=0.0)
        negative_payment = pw.FloatField(default=0.0)
        positive_resource = pw.FloatField(default=0.0)
        negative_resource = pw.FloatField(default=0.0)

        class Meta:
            db_table = "localrank"

    @migrator.create_model
    class NeighbourLocRank(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        node_id = pw.CharField(max_length=255)
        about_node_id = pw.CharField(max_length=255)
        requesting_trust_value = pw.FloatField(default=0.0)
        computing_trust_value = pw.FloatField(default=0.0)

        class Meta:
            db_table = "neighbourlocrank"

            primary_key = pw.CompositeKey('node_id', 'about_node_id')

    @migrator.create_model
    class NetworkMessage(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        local_role = pw.EnumField(Actor)
        remote_role = pw.EnumField(Actor)
        node = pw.CharField(max_length=255)
        task = pw.CharField(index=True, max_length=255, null=True)
        subtask = pw.CharField(index=True, max_length=255, null=True)
        msg_date = pw.DateTimeField()
        msg_cls = pw.CharField(max_length=255)
        msg_data = pw.BlobField()

        class Meta:
            db_table = "networkmessage"

    @migrator.create_model
    class Payment(pw.Model):
        subtask = pw.CharField(max_length=255, primary_key=True)
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        status = pw.EnumField(PaymentStatus, default=PaymentStatus.awaiting,
                              index=True)
        payee = pw.RawCharField()
        value = pw.BigIntegerField()
        details = pw.PaymentDetailsField()
        processed_ts = pw.IntegerField(null=True)

        class Meta:
            db_table = "payment"

    @migrator.create_model
    class Performance(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        environment_id = pw.CharField(max_length=255, unique=True)
        value = pw.FloatField(default=0.0)

        class Meta:
            db_table = "performance"

    @migrator.create_model
    class Stats(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        name = pw.CharField(max_length=255)
        value = pw.CharField(max_length=255)

        class Meta:
            db_table = "stats"

    @migrator.create_model
    class TaskPreset(pw.Model):
        created_date = pw.DateTimeField(default=dt.datetime.now)
        modified_date = pw.DateTimeField(default=dt.datetime.now)
        name = pw.CharField(max_length=255)
        task_type = pw.CharField(index=True, max_length=255)
        data = pw.JsonField()

        class Meta:
            db_table = "taskpreset"

            primary_key = pw.CompositeKey('task_type', 'name')



def rollback(migrator, database, fake=False, **kwargs):
    """Write your rollback migrations here."""

    migrator.remove_model('taskpreset')

    migrator.remove_model('stats')

    migrator.remove_model('performance')

    migrator.remove_model('payment')

    migrator.remove_model('networkmessage')

    migrator.remove_model('neighbourlocrank')

    migrator.remove_model('localrank')

    migrator.remove_model('knownhosts')

    migrator.remove_model('income')

    migrator.remove_model('hardwarepreset')

    migrator.remove_model('globalrank')

    migrator.remove_model('generickeyvalue')

    migrator.remove_model('expectedincome')

    migrator.remove_model('basemodel')

    migrator.remove_model('account')

