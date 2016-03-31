from peewee import SqliteDatabase, Model, CharField, IntegerField, FloatField, DateTimeField, CompositeKey

import datetime
import appdirs
import os

DATABASE_NAME = os.path.join(appdirs.user_data_dir('golem'), 'golem.db')
NEUTRAL_TRUST = 0.0


db = SqliteDatabase(None, threadlocals=True, pragmas=(('foreign_keys', True), ('busy_timeout', 30000)))


class Database:
    def __init__(self, name=DATABASE_NAME):

        self.name = name
        self.db = db

        db.init(name)
        db.connect()
        self.create_database()

    @staticmethod
    def create_database():
        db.create_tables([LocalRank, GlobalRank, NeighbourLocRank, Payment, ReceivedPayment], safe=True)


class BaseModel(Model):
    class Meta:
        database = db
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)


##################
# PAYMENT MODELS #
##################


class Payment(BaseModel):
    """ Represents payments that nodes on this machine make to other nodes
    """
    to_node_id = CharField()
    task = CharField()
    val = IntegerField()
    state = CharField()
    details = CharField(default="")

    class Meta:
        database = db
        primary_key = CompositeKey('to_node_id', 'task')


class ReceivedPayment(BaseModel):
    """ Represent payments that nodes on this machine receive from other nodes
    """
    from_node_id = CharField()
    task = CharField()
    val = IntegerField()
    expected_val = IntegerField()
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
