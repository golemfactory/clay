from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField, DateTimeField, IntegrityError

import datetime
import random

DATABASE_NAME = 'golem.db'
START_BUDGET = 42000000

db = SqliteDatabase( DATABASE_NAME, threadlocals=True)

class Database:
    def __init__( self ):
        self.db = db
        self.name = DATABASE_NAME

        db.connect()
        self.createDatabase()

    def createDatabase(self):
        db.create_tables([Node, Bank, LocalRank], safe=True)

    def checkNode(self, nodeId ):
        with db.transaction():
            nodes = [ n for n in Node.select().where( Node.nodeId == nodeId )]
            if len( nodes ) == 0:
                Node.create( nodeId = nodeId )
            bank = [ n for n in Bank.select().where( Bank.nodeId == nodeId )]
            if len( bank ) == 0:
                Bank.create( nodeId = nodeId )

    def increaseComputingTrust(self, nodeId, trustMod ):
        try:
            with db.transaction():
                LocalRank.create(nodeId=nodeId, positiveComputed=trustMod)
        except IntegrityError:
            LocalRank.update(positiveComputed = LocalRank.positiveComputed + trustMod).where(nodeId == nodeId).execute()

    def decreaseComputingTrust(self, nodeId, trustMod):
        try:
            with db.transaction():
                LocalRank.create(nodeId = nodeId, negativeComputed = trustMod)
        except IntegrityError:
            LocalRank.update(negativeComputed = LocalRank.negativeComputed + trustMod).where(nodeId == nodeId).execute()

    def increaseRequesterTrust(self, nodeId, trustMod):
        try:
            with db.transaction():
                LocalRank.create(nodeId = nodeId, positiveRequested = trustMod)
        except IntegrityError:
            LocalRank.update(positiveRequested = LocalRank.positiveRequested + trustMod).where(nodeId == nodeId).execute()

    def decreaseRequesterTrust(self, nodeId, trustMod):
        try:
            with db.transaction():
                LocalRank.create(nodeId = nodeId, negativeRequested = trustMod)
        except IntegrityError:
            LocalRank.update(negativeRequested = LocalRank.negativeRequested + trustMod).where(nodeId == nodeId).execute()


class BaseModel( Model ):
    class Meta:
        database = db

class Node( BaseModel ):
    nodeId = CharField( primary_key=True )

class Bank( BaseModel ):
    nodeId = ForeignKeyField( Node, related_name='has', unique=True )
    val = FloatField( default = START_BUDGET )
    created_date = DateTimeField( default = datetime.datetime.now )

class LocalRank( BaseModel ):
    nodeId = CharField( unique=True )
    positiveComputed = FloatField( default = 0.0 )
    negativeComputed = FloatField( default = 0.0 )
    positiveRequested = FloatField( default = 0.0 )
    negativeRequested = FloatField( default = 0.0 )
