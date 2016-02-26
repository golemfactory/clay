from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField, DateTimeField, CompositeKey

import datetime
import appdirs
import os

DATABASE_NAME = os.path.join(appdirs.user_data_dir('golem'), 'golem.db')
START_BUDGET = 42000000
NEUTRAL_TRUST = 0.0


class SqliteFKTimeoutDatabase(SqliteDatabase):
    def initialize_connection(self, conn):
        self.execute_sql('PRAGMA foreign_keys = ON')
        self.execute_sql('PRAGMA busy_timeout = 30000')


db = SqliteFKTimeoutDatabase(None, threadlocals=True)


class Database:
    def __init__(self, name=None):
        if name is None:
            name = DATABASE_NAME

        self.name = name
        self.db = db

        db.init(name)
        db.connect()
        self.create_database()

    def create_database(self):
        db.create_tables([Node, Bank, LocalRank, GlobalRank, NeighbourLocRank, Payment, ReceivedPayment], safe=True)

    def check_node(self, node_id):
        with db.transaction():
            nodes = [n for n in Node.select().where(Node.node_id == node_id)]
            if len(nodes) == 0:
                Node.create(node_id=node_id)
            bank = [n for n in Bank.select().where(Bank.node_id == node_id)]
            if len(bank) == 0:
                Bank.create(node_id=node_id)


class BaseModel(Model):
    class Meta:
        database = db
    created_date = DateTimeField(default=datetime.datetime.now)
    modified_date = DateTimeField(default=datetime.datetime.now)


###############
# NODE MODELS #
###############

class Node(BaseModel):
    """ Represent nodes that are active on this machine
    """
    node_id = CharField(primary_key=True)


##################
# PAYMENT MODELS #
##################

class Bank(BaseModel):
    """ Represents nodes local account (just for test purpose)
    """
    node_id = ForeignKeyField(Node, related_name='has', unique=True)
    val = FloatField(default=START_BUDGET)


class Payment(BaseModel):
    """ Represents payments that nodes on this machine make to other nodes
    """
    to_node_id = CharField()
    task = CharField()
    val = FloatField()
    state = CharField()

    class Meta:
        database = db
        primary_key = CompositeKey('to_node_id', 'task')


class ReceivedPayment(BaseModel):
    """ Represent payments that nodes on this machine receive from other nodes
    """
    from_node_id = CharField()
    task = CharField()
    val = FloatField()
    expected_val = FloatField()
    state = CharField()

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
