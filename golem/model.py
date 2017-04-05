from __future__ import absolute_import


import datetime
from ethereum.utils import denoms
import jsonpickle as json
import logging
from enum import Enum
from os import path

from peewee import (SqliteDatabase, Model, CharField, IntegerField, FloatField,
                    DateTimeField, TextField, CompositeKey, BooleanField)


log = logging.getLogger('golem.db')

NEUTRAL_TRUST = 0.0

# Indicates how many KnownHosts can be stored in the DB
MAX_STORED_HOSTS = 4


db = SqliteDatabase(None, threadlocals=True,
                    pragmas=(('foreign_keys', True), ('busy_timeout', 30000)))


class Database:
    # Database user schema version, bump to recreate the database
    SCHEMA_VERSION = 4

    def __init__(self, datadir):
        # TODO: Global database is bad idea. Check peewee for other solutions.
        self.db = db
        db.init(path.join(datadir, 'golem.db'))
        db.connect()
        self.create_database()

    @staticmethod
    def _get_user_version():
        return db.execute_sql('PRAGMA user_version').fetchone()[0]

    @staticmethod
    def _set_user_version(version):
        db.execute_sql('PRAGMA user_version = {}'.format(version))

    @staticmethod
    def create_database():
        tables = [
            Account,
            ExpectedIncome,
            GlobalRank,
            Income,
            KnownHosts,
            LocalRank,
            NeighbourLocRank,
            Payment,
            ReceivedPayment,
            Stats,
        ]
        version = Database._get_user_version()
        if version != Database.SCHEMA_VERSION:
            log.info("New database version {}, previous {}".format(Database.SCHEMA_VERSION, version))
            db.drop_tables(tables, safe=True)
            Database._set_user_version(Database.SCHEMA_VERSION)
        db.create_tables(tables, safe=True)

    def close(self):
        if not self.db.is_closed():
            self.db.close()


class BaseModel(Model):
    class Meta:
        database = db
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)


##################
# PAYMENT MODELS #
##################

class RawCharField(CharField):
    """ Char field without auto utf-8 encoding."""

    def db_value(self, value):
        return unicode(value.encode('hex'))

    def python_value(self, value):
        return value.decode('hex')


class BigIntegerField(CharField):
    """ Standard Integer field is limited to 2^63-1. This field extends the
        range by storing the numbers as hex-encoded char strings.
    """

    def db_value(self, value):
        if type(value) not in (int, long):
            raise TypeError("Value {} is not an integer".format(value))
        return format(value, 'x')

    def python_value(self, value):
        return int(value, 16)


class EnumField(IntegerField):
    """ Database field that maps enum type to integer."""

    def __init__(self, enum_type, *args, **kwargs):
        super(EnumField, self).__init__(*args, **kwargs)
        self.enum_type = enum_type

    def db_value(self, value):
        if not isinstance(value, self.enum_type):
            raise TypeError("Expected {} type".format(self.enum_type.__name__))
        return value.value  # Get the integer value of an enum.

    def python_value(self, value):
        return self.enum_type(value)


class JsonField(TextField):
    """ Database field that stores a Python value in JSON format. """

    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)


class PaymentStatus(Enum):
    """ The status of a payment. """
    awaiting = 1    # Created but not introduced to the payment network.
    sent = 2        # Sent to the payment network.
    confirmed = 3   # Confirmed on the payment network.


class Payment(BaseModel):
    """ Represents payments that nodes on this machine make to other nodes
    """
    subtask = CharField(primary_key=True)
    status = EnumField(enum_type=PaymentStatus, index=True, default=PaymentStatus.awaiting)
    payee = RawCharField()
    value = BigIntegerField()
    details = JsonField()

    def __init__(self, *args, **kwargs):
        super(Payment, self).__init__(*args, **kwargs)
        # For convenience always have .details as a dictionary
        if self.details is None:
            self.details = {}

    def __repr__(self):
        tx = self.details.get('tx', 'NULL')
        return "<Payment stid: %r v: %.3f s: %r tx: %s>" % (self.subtask, self.value/denoms.ether, self.status, tx)


class ExpectedIncome(BaseModel):
    sender_node = CharField()
    task = CharField()
    subtask = CharField()
    value = BigIntegerField()


class Income(BaseModel):
    """Payments received from other nodes."""
    sender_node = CharField()
    task = CharField()
    subtask = CharField()
    transaction = CharField()
    value = BigIntegerField()

    class Meta:
        database = db
        primary_key = CompositeKey('sender_node', 'subtask')

class ReceivedPayment(BaseModel):
    """ Represent payments that nodes on this machine receive from other nodes
    """
    from_node_id = CharField()
    task = CharField()
    val = BigIntegerField()
    expected_val = BigIntegerField()
    state = CharField()
    details = CharField(default="")

    class Meta:
        database = db
        primary_key = CompositeKey('from_node_id', 'task')


##################
# RANKING MODELS #
##################

class LocalRank(BaseModel):
    """ Represent nodes experience with other nodes, number of positive and
    negative interactions.
    """
    node_id = CharField(unique=True)
    positive_computed = FloatField(default=0.0)
    negative_computed = FloatField(default=0.0)
    wrong_computed = FloatField(default=0.0)
    positive_requested = FloatField(default=0.0)
    negative_requested = FloatField(default=0.0)
    positive_payment = FloatField(default=0.0)
    negative_payment = FloatField(default=0.0)
    positive_resource = FloatField(default=0.0)
    negative_resource = FloatField(default=0.0)


class GlobalRank(BaseModel):
    """ Represents global ranking vector estimation
    """
    node_id = CharField(unique=True)
    requesting_trust_value = FloatField(default=NEUTRAL_TRUST)
    computing_trust_value = FloatField(default=NEUTRAL_TRUST)
    gossip_weight_computing = FloatField(default=0.0)
    gossip_weight_requesting = FloatField(default=0.0)


class NeighbourLocRank(BaseModel):
    """ Represents neighbour trust level for other nodes
    """
    node_id = CharField()
    about_node_id = CharField()
    requesting_trust_value = FloatField(default=NEUTRAL_TRUST)
    computing_trust_value = FloatField(default=NEUTRAL_TRUST)

    class Meta:
        database = db
        primary_key = CompositeKey('node_id', 'about_node_id')


##################
# NETWORK MODELS #
##################

class KnownHosts(BaseModel):
    ip_address = CharField()
    port = IntegerField()
    last_connected = DateTimeField(default=datetime.datetime.now)
    is_seed = BooleanField(default=False)

    class Meta:
        database = db
        indexes = (
            (('ip_address', 'port'), True),  # unique index
        )


##################
# ACCOUNT MODELS #
##################

class Account(BaseModel):
    node_id = CharField(unique=True)
    description = TextField(default="")

    class Meta:
        database = db


class Stats(BaseModel):
    name = CharField()
    value = CharField()

    class Meta:
        database = db
