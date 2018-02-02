import datetime
import json
import logging
import pickle
from enum import Enum
from os import path
# Type is used for old-style (pre Python 3.6) type annotation
from typing import Optional, Type  # pylint: disable=unused-import


from ethereum.utils import denoms
from golem_messages import message
from peewee import (BooleanField, CharField, CompositeKey, DateTimeField,
                    FloatField, IntegerField, Model, SmallIntegerField,
                    SqliteDatabase, TextField, BlobField)
from playhouse.shortcuts import RetryOperationalError

from golem.core.simpleserializer import DictSerializable
from golem.network.p2p.node import Node
from golem.ranking.helper.trust_const import NEUTRAL_TRUST
from golem.utils import decode_hex, encode_hex

log = logging.getLogger('golem.db')


class GolemSqliteDatabase(RetryOperationalError, SqliteDatabase):

    def sequence_exists(self, seq):
        raise NotImplementedError()


# Indicates how many KnownHosts can be stored in the DB
MAX_STORED_HOSTS = 4
db = GolemSqliteDatabase(None, threadlocals=True,
                         pragmas=(
                             ('foreign_keys', True),
                             ('busy_timeout', 1000),
                             ('journal_mode', 'WAL')))


class Database:
    # Database user schema version, bump to recreate the database
    SCHEMA_VERSION = 10

    def __init__(self, datadir):
        # TODO: Global database is bad idea. Check peewee for other solutions.
        self.db = db
        db.init(path.join(datadir, 'golem.db'))
        db.connect()
        self.create_database()

    @staticmethod
    def _get_user_version() -> int:
        return int(db.execute_sql('PRAGMA user_version').fetchone()[0])

    @staticmethod
    def _set_user_version(version: int) -> None:
        db.execute_sql('PRAGMA user_version = {}'.format(version))

    @staticmethod
    def create_database() -> None:
        tables = [
            GenericKeyValue,
            Account,
            ExpectedIncome,
            GlobalRank,
            HardwarePreset,
            Income,
            KnownHosts,
            LocalRank,
            NeighbourLocRank,
            Payment,
            Stats,
            TaskPreset,
            Performance,
            NetworkMessage
        ]
        version = Database._get_user_version()
        if version != Database.SCHEMA_VERSION:
            log.info("New database version {}, previous {}".format(
                Database.SCHEMA_VERSION, version))
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


class GenericKeyValue(BaseModel):
    key = CharField(primary_key=True)
    value = CharField(null=True)


##################
# PAYMENT MODELS #
##################


class RawCharField(CharField):
    """ Char field without auto utf-8 encoding."""

    def db_value(self, value):
        return str(encode_hex(value))

    def python_value(self, value):
        return decode_hex(value)


class BigIntegerField(CharField):
    """ Standard Integer field is limited to 2^63-1. This field extends the
        range by storing the numbers as hex-encoded char strings.
    """

    def db_value(self, value):
        if not isinstance(value, int):
            raise TypeError("Value {} is not an integer".format(value))
        return format(value, 'x')

    def python_value(self, value):
        if value is not None:
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


class DictSerializableJSONField(TextField):
    """ Database field that stores a Node in JSON format. """
    objtype = None  # type: Type[DictSerializable]

    def db_value(self, value: Optional[DictSerializable]) -> str:
        if value is None:
            return json.dumps(None)
        return json.dumps(value.to_dict())

    def python_value(self, value: str) -> DictSerializable:
        return self.objtype.from_dict(json.loads(value))


class PaymentStatus(Enum):
    """ The status of a payment. """
    awaiting = 1  # Created but not introduced to the payment network.
    sent = 2  # Sent to the payment network.
    confirmed = 3  # Confirmed on the payment network.


class PaymentDetails(DictSerializable):
    def __init__(self,
                 node_info: Optional[Node] = None,
                 fee: Optional[int] = None,
                 block_hash: Optional[str] = None,
                 block_number: Optional[int] = None,
                 check: Optional[bool] = None,
                 tx: Optional[str] = None) -> None:
        self.node_info = node_info
        self.fee = fee
        self.block_hash = block_hash
        self.block_number = block_number
        self.check = check
        self.tx = tx

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        if self.node_info:
            d['node_info'] = self.node_info.to_dict()
        return d

    @staticmethod
    def from_dict(data: dict) -> 'PaymentDetails':
        det = PaymentDetails()
        det.__dict__.update(data)
        det.__dict__['node_info'] = Node.from_dict(data['node_info'])
        return det

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PaymentDetails):
            raise TypeError(
                "Mismatched types: expected PaymentDetails, got {}".format(
                    type(other)))
        return self.__dict__ == other.__dict__


class NodeField(DictSerializableJSONField):
    """ Database field that stores a Node in JSON format. """
    objtype = Node


class PaymentDetailsField(DictSerializableJSONField):
    """ Database field that stores a PaymentDetails in JSON format. """
    objtype = PaymentDetails


class Payment(BaseModel):
    """ Represents payments that nodes on this machine make to other nodes
    """
    subtask = CharField(primary_key=True)
    status = EnumField(enum_type=PaymentStatus,
                       index=True,
                       default=PaymentStatus.awaiting)
    payee = RawCharField()
    value = BigIntegerField()
    details = PaymentDetailsField()
    processed_ts = IntegerField(null=True)

    def __init__(self, *args, **kwargs):
        super(Payment, self).__init__(*args, **kwargs)
        # For convenience always have .details as a dictionary
        if self.details is None:
            self.details = PaymentDetails()

    def __repr__(self) -> str:
        tx = self.details.tx
        bn = self.details.block_number
        return "<Payment sbid:{!r} v:{:.3f} s:{!r} tx:{!r} bn:{!r} ts:{!r}>"\
            .format(
                self.subtask,
                float(self.value) / denoms.ether,
                self.status,
                tx,
                bn,
                self.processed_ts
            )

    def get_sender_node(self) -> Optional[Node]:
        return self.details.node_info


class ExpectedIncome(BaseModel):
    sender_node = CharField()
    sender_node_details = NodeField()
    subtask = CharField()
    value = BigIntegerField()
    accepted_ts = IntegerField(null=True)

    def __repr__(self):
        return "<ExpectedIncome: {!r} v:{:.3f}>"\
            .format(self.subtask, self.value)

    def get_sender_node(self):
        return self.sender_node_details


class Income(BaseModel):
    """Payments received from other nodes."""
    sender_node = CharField()
    subtask = CharField()
    transaction = CharField()
    value = BigIntegerField()

    class Meta:
        database = db
        primary_key = CompositeKey('sender_node', 'subtask')

    def __repr__(self):
        return "<Income: {!r} v:{:.3f} tid:{!r}>"\
            .format(
                self.subtask,
                self.value,
                self.transaction,
            )


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

    class Meta:
        database = db


class Stats(BaseModel):
    name = CharField()
    value = CharField()

    class Meta:
        database = db


class HardwarePreset(BaseModel):
    name = CharField(null=False, index=True, unique=True)

    cpu_cores = SmallIntegerField(null=False)
    memory = IntegerField(null=False)
    disk = IntegerField(null=False)

    def to_dict(self):
        return {
            'name': str(self.name),
            'cpu_cores': self.cpu_cores,
            'memory': self.memory,
            'disk': self.disk
        }

    def apply(self, dictionary: dict) -> None:
        self.cpu_cores = dictionary['cpu_cores']
        self.memory = dictionary['memory']
        self.disk = dictionary['disk']

    class Meta:
        database = db


##############
# APP MODELS #
##############


class TaskPreset(BaseModel):
    name = CharField(null=False)
    task_type = CharField(null=False, index=True)
    data = JsonField(null=False)

    class Meta:
        database = db
        primary_key = CompositeKey('task_type', 'name')


class Performance(BaseModel):
    """ Keeps information about benchmark performance """
    environment_id = CharField(null=False, index=True, unique=True)
    value = FloatField(default=0.0)

    class Meta:
        database = db

    @classmethod
    def update_or_create(cls, env_id, performance):
        try:
            perf = Performance.get(Performance.environment_id == env_id)
            perf.value = performance
            perf.save()
        except Performance.DoesNotExist:
            perf = Performance(environment_id=env_id, value=performance)
            perf.save()


##################
# MESSAGE MODELS #
##################


class Actor(Enum):
    Concent = "concent"
    Requestor = "requestor"
    Provider = "provider"


class NetworkMessage(BaseModel):
    local_role = EnumField(Actor, null=False)
    remote_role = EnumField(Actor, null=False)

    # The node on the other side of the communication.
    # It can be a receiver or a sender, depending on local_role,
    # remote_role and msg_cls.
    node = CharField(null=False)
    task = CharField(null=True, index=True)
    subtask = CharField(null=True, index=True)

    msg_date = DateTimeField(null=False)
    msg_cls = CharField(null=False)
    msg_data = BlobField(null=False)

    def as_message(self) -> message.Message:
        msg = pickle.loads(self.msg_data)
        return msg
