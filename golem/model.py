import datetime
import enum
import inspect
import json
import pickle
import sys
import time
from typing import Optional

from eth_utils import decode_hex, encode_hex
from ethereum.utils import denoms
import golem_messages
from golem_messages import datastructures as msg_dt
from golem_messages import exceptions as msg_exceptions
from golem_messages import message
from golem_messages.datastructures import p2p as dt_p2p
from peewee import (
    BlobField,
    BooleanField,
    CharField,
    CompositeKey,
    DateTimeField,
    Field,
    FloatField,
    IntegerField,
    Model,
    SmallIntegerField,
    TextField,
)
import semantic_version

from golem.core import common
from golem.core.simpleserializer import DictSerializable
from golem.database import GolemSqliteDatabase
from golem.ranking.helper.trust_const import NEUTRAL_TRUST
from golem.ranking import ProviderEfficacy


# TODO: migrate to golem.database. issue #2415
db = GolemSqliteDatabase(None, threadlocals=True,
                         pragmas=(
                             ('foreign_keys', True),
                             ('busy_timeout', 1000),
                             ('journal_mode', 'WAL')))


class BaseModel(Model):
    class Meta:
        database = db

    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)

    def refresh(self):
        """
        https://github.com/coleifer/peewee/issues/686#issuecomment-130548126
        :return: Refreshed version of the object retrieved from db
        """
        return type(self).get(self._pk_expr())


class GenericKeyValue(BaseModel):
    key = CharField(primary_key=True)
    value = CharField(null=True)


##################
# PAYMENT MODELS #
##################


class RawCharField(CharField):
    """ Char field without auto utf-8 encoding."""

    def db_value(self, value):
        return encode_hex(value)[2:]

    def python_value(self, value):
        return decode_hex(value)


class HexIntegerField(CharField):
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
        return None


class FixedLengthHexField(CharField):
    EXPECTED_LENGTH: int = 0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, max_length=self.EXPECTED_LENGTH, **kwargs)

    def db_value(self, value: str):
        value = super().db_value(value)
        current_len = len(value)
        if len(value) != self.EXPECTED_LENGTH:
            raise ValueError(
                "Value {value} has length of {has}"
                " not {should} characters".format(
                    value=value,
                    has=current_len,
                    should=self.EXPECTED_LENGTH,
                ),
            )
        return value


class BlockchainTransactionField(FixedLengthHexField):
    EXPECTED_LENGTH = 66


class EnumFieldBase:
    enum_type = None

    def db_value(self, value):
        if isinstance(value, self.enum_type):
            return value.value  # Get the base-type value of an enum.

        value = self.coerce(value)  # noqa pylint:disable=no-member
        enum_vals = [e.value for e in self.enum_type]
        if value not in enum_vals:
            raise TypeError(
                "Expected {} type or one of {}".format(
                    self.enum_type.__name__, enum_vals))

        return value

    def python_value(self, value):
        # pylint: disable=not-callable
        return self.enum_type(value)


class ProviderEfficacyField(CharField):

    def db_value(self, value):
        if not isinstance(value, ProviderEfficacy):
            raise TypeError("Value {} is not an instance of ProviderEfficacy"
                            .format(value))
        return value.serialize()

    def python_value(self, value):
        if value is not None:
            return ProviderEfficacy.deserialize(value)
        return None


class EnumField(EnumFieldBase, IntegerField):
    """ Database field that maps enum type to integer."""

    def __init__(self, enum_type, *args, **kwargs):
        super(EnumField, self).__init__(*args, **kwargs)
        self.enum_type = enum_type


class StringEnumField(EnumFieldBase, CharField):
    """ Database field that maps enum types to strings."""

    def __init__(self, enum_type, *args, max_length=255, **kwargs):
        super().__init__(max_length, *args, **kwargs)
        self.enum_type = enum_type


class JsonField(TextField):
    """ Database field that stores a Python value in JSON format. """

    def db_value(self, value):
        return json.dumps(value)

    def python_value(self, value):
        return json.loads(value)


class DictSerializableJSONField(TextField):
    """ Database field that stores a Node in JSON format. """
    objtype: DictSerializable

    def db_value(self, value: Optional[DictSerializable]) -> str:
        if value is None:
            return json.dumps(None)
        return json.dumps(value.to_dict())

    def python_value(self, value: str) -> DictSerializable:
        if issubclass(self.objtype, msg_dt.Container):  # type: ignore
            # pylint: disable=not-callable
            return self.objtype(**json.loads(value))  # type: ignore
        return self.objtype.from_dict(json.loads(value))


class PaymentStatus(enum.Enum):
    """ The status of a payment. """
    awaiting = 1  # Created but not introduced to the payment network.
    sent = 2  # Sent to the payment network.
    confirmed = 3  # Confirmed on the payment network.
    # overdue - As a Provider try to use Concent
    # reasons may include:
    #  * Requestor made a transaction that didn’t cover this payment
    #    (can be detected earlier)
    #  * Requestor didn’t make a transaction at all (actual overdue payment)
    # As a Requestor reasons may include:
    #  * insufficient ETH/GNT
    #  * Golem bug
    overdue = 4

    # Workarounds for peewee_migration

    def __repr__(self):
        return '{}.{}'.format(self.__class__.__name__, self.name)

    @property
    def __self__(self):
        return self


class PaymentDetails(DictSerializable):
    def __init__(self,
                 node_info: Optional[dt_p2p.Node] = None,
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
        if data['node_info']:
            try:
                det.node_info = dt_p2p.Node(**data['node_info'])
            except msg_exceptions.FieldError:
                det.node_info = None
        return det

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PaymentDetails):
            raise TypeError(
                "Mismatched types: expected PaymentDetails, got {}".format(
                    type(other)))
        return self.__dict__ == other.__dict__


class NodeField(DictSerializableJSONField):
    """ Database field that stores a Node in JSON format. """
    objtype = dt_p2p.Node


class PaymentDetailsField(DictSerializableJSONField):
    """ Database field that stores a PaymentDetails in JSON format. """
    objtype = PaymentDetails


class PaymentStatusField(EnumField):
    """ Database field that stores PaymentStatusField objects as integers. """
    def __init__(self, *args, **kwargs):
        super().__init__(PaymentStatus, *args, **kwargs)


class VersionField(CharField):
    """Semantic version field"""

    def db_value(self, value):
        if not isinstance(value, semantic_version.Version):
            raise TypeError(f"Value {value} is not a semantic version")
        return str(value)

    def python_value(self, value):
        if value is not None:
            return semantic_version.Version(value)
        return None


class Payment(BaseModel):
    """ Represents payments that nodes on this machine make to other nodes
    """
    subtask = CharField(primary_key=True)
    status = PaymentStatusField(index=True, default=PaymentStatus.awaiting)
    payee = RawCharField()
    value = HexIntegerField()
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


class DepositPayment(BaseModel):
    tx = BlockchainTransactionField(primary_key=True)
    value = HexIntegerField()
    status = PaymentStatusField(index=True, default=PaymentStatus.awaiting)
    fee = HexIntegerField(null=True)

    class Meta:
        database = db

    def __repr__(self):
        return "<DepositPayment: {value} s:{status} tx:{tx}>"\
            .format(
                value=self.value,
                status=self.status,
                tx=self.tx,
            )


class Income(BaseModel):
    sender_node = CharField()
    subtask = CharField()
    payer_address = CharField()
    value = HexIntegerField()
    value_received = HexIntegerField(default=0)
    accepted_ts = IntegerField(null=True)
    transaction = CharField(null=True)
    overdue = BooleanField(default=False)
    settled_ts = IntegerField(null=True)  # set if settled by the Concent

    class Meta:
        database = db
        primary_key = CompositeKey('sender_node', 'subtask')

    def __repr__(self):
        return "<Income: {!r} v:{:.3f} accepted_ts:{!r} tid:{!r}>"\
            .format(
                self.subtask,
                self.value,
                self.accepted_ts,
                self.transaction,
            )

    @property
    def value_expected(self):
        return self.value - self.value_received

    @property
    def status(self) -> PaymentStatus:
        if self.value_expected == 0:
            return PaymentStatus.confirmed
        if self.overdue:
            return PaymentStatus.overdue
        return PaymentStatus.awaiting

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
    requestor_efficiency = FloatField(default=None, null=True)
    requestor_assigned_sum = HexIntegerField(default=0)
    requestor_paid_sum = HexIntegerField(default=0)
    provider_efficiency = FloatField(default=1.0)
    provider_efficacy = ProviderEfficacyField(
        default=ProviderEfficacy(0., 0., 0., 0.))


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
    metadata = JsonField(default='{}')

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
    min_accepted_step = FloatField(default=300.0)

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


class DockerWhitelist(BaseModel):
    repository = CharField(primary_key=True)


##################
# MESSAGE MODELS #
##################


class Actor(enum.Enum):
    Concent = "concent"
    Requestor = "requestor"
    Provider = "provider"


class ActorField(StringEnumField):
    """ Database field that stores Actor objects as strings. """
    def __init__(self, *args, **kwargs):
        super().__init__(Actor, *args, **kwargs)


class NetworkMessage(BaseModel):
    local_role = ActorField(null=False)
    remote_role = ActorField(null=False)

    # The node we are exchanging messages with. Can be a receiver or a sender,
    # which is determined by local_role, remote_role and msg_cls.
    node = CharField(null=False)
    task = CharField(null=True, index=True)
    subtask = CharField(null=True, index=True)

    msg_date = DateTimeField(null=False)
    msg_cls = CharField(null=False)
    msg_data = BlobField(null=False)

    def as_message(self) -> message.base.Message:
        msg = pickle.loads(self.msg_data)
        return msg


class QueuedMessage(BaseModel):
    node = CharField(null=False, index=True)
    msg_version = VersionField(null=False)
    msg_cls = CharField(null=False)
    msg_data = BlobField(null=False)

    @classmethod
    def from_message(cls, node_id: str, msg: message.base.Message):
        instance = cls()
        instance.node = node_id
        instance.msg_cls = '.'.join(
            [msg.__class__.__module__, msg.__class__.__qualname__, ],
        )
        instance.msg_version = semantic_version.Version(
            golem_messages.__version__,
        )
        instance.msg_data = golem_messages.dump(msg, None, None)
        return instance

    def as_message(self) -> message.base.Message:
        message.base.verify_version(str(self.msg_version))
        msg = golem_messages.load(
            self.msg_data,
            None,
            None,
            check_time=False,
        )
        msg.header = msg_dt.MessageHeader(
            msg.header[0],
            int(time.time()),
            False,
        )
        msg.sig = None
        return msg

    def __str__(self):
        node = self.node or ''
        return (
            f"{ self.__class__.__name__ }"
            f" node={common.short_node_id(node)}"
            f", version={self.msg_version}"
            f", class={self.msg_cls}"
        )


class CachedNode(BaseModel):
    node = CharField(null=False, index=True, unique=True)
    node_field = NodeField(null=False)

    def __str__(self):
        # pylint: disable=no-member
        node_name = self.node_field.node_name if self.node_field else ''
        node_id = self.node or ''
        return (
            f"{common.node_info_str(node_name, node_id)}"
        )

    def __repr__(self):
        return (
            f"<{self.__class__.__module__}.{self.__class__.__qualname__}:"
            f" {self}>"
        )


def collect_db_models(module: str = __name__):
    return inspect.getmembers(
        sys.modules[module],
        lambda cls: (
            inspect.isclass(cls) and
            issubclass(cls, BaseModel) and
            cls is not BaseModel
        )
    )


def collect_db_fields(module: str = __name__):
    return inspect.getmembers(
        sys.modules[module],
        lambda cls: (
            inspect.isclass(cls) and
            issubclass(cls, Field)
        )
    )


DB_FIELDS = [cls for _, cls in collect_db_fields()]
DB_MODELS = [cls for _, cls in collect_db_models()]
