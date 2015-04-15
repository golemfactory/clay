from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField, DateTimeField, CompositeKey

import datetime

DATABASE_NAME = 'golem.db'
START_BUDGET = 42000000

class SqliteFKTimeoutDatabase( SqliteDatabase ):
    def initalize_connection(self, conn):
        self.execute_sql('PRAGMA foreign_keys = ON')
        self.execute_sql('PRAGMA busy_timeout = 30000')

db = SqliteFKTimeoutDatabase( DATABASE_NAME, threadlocals=True)

class Database:
    def __init__( self ):
        self.db = db
        self.name = DATABASE_NAME

        db.connect()
        self.createDatabase()

    def createDatabase(self):
        db.create_tables([Node, Bank, LocalRank, GlobalRank, NeighbourLocRank], safe=True)

    def checkNode(self, nodeId ):
        with db.transaction():
            nodes = [ n for n in Node.select().where( Node.nodeId == nodeId )]
            if len( nodes ) == 0:
                Node.create( nodeId = nodeId )
            bank = [ n for n in Bank.select().where( Bank.nodeId == nodeId )]
            if len( bank ) == 0:
                Bank.create( nodeId = nodeId )

class BaseModel( Model ):
    class Meta:
        database = db

class Node( BaseModel ):
    nodeId = CharField( primary_key=True )
    created_date = DateTimeField( default = datetime.datetime.now )
    modified_date = DateTimeField( default = datetime.datetime.now )

class Bank( BaseModel ):
    nodeId = ForeignKeyField( Node, related_name='has', unique=True )
    val = FloatField( default = START_BUDGET )
    created_date = DateTimeField( default = datetime.datetime.now )
    modified_date = DateTimeField( default = datetime.datetime.now )

class LocalRank( BaseModel ):
    nodeId = CharField( unique=True )
    positiveComputed = FloatField( default = 0.0 )
    negativeComputed = FloatField( default = 0.0 )
    positiveRequested = FloatField( default = 0.0 )
    negativeRequested = FloatField( default = 0.0 )
    positivePayment = FloatField( default = 0.0 )
    negativePayment = FloatField( default = 0.0 )
    positiveResource = FloatField( default = 0.0 )
    negativeResource = FloatField( default = 0.0 )
    created_date = DateTimeField( default = datetime.datetime.now )
    modified_date = DateTimeField( default = datetime.datetime.now )

class GlobalRank( BaseModel ):
    nodeId = CharField( unique=True )
    requestingTrustValue = FloatField( default = 0.0 )
    computingTrustValue = FloatField( default = 0.0 )
    gossipWeightComputing = FloatField( default = 0.0 )
    gossipWeightRequesting = FloatField( default = 0.0)
    created_date = DateTimeField( default = datetime.datetime.now )
    modified_date = DateTimeField( default = datetime.datetime.now )

class NeighbourLocRank( BaseModel ):
    nodeId = CharField()
    aboutNodeId = CharField()
    requestingTrustValue = FloatField( default = 0.0 )
    computingTrustValue = FloatField( default = 0.0 )
    created_date = DateTimeField( default = datetime.datetime.now )
    modified_date = DateTimeField( default = datetime.datetime.now )

    class Meta:
        primary_key = CompositeKey( 'nodeId', 'aboutNodeId' )


