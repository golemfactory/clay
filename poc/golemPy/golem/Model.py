from peewee import SqliteDatabase, Model, CharField, ForeignKeyField, FloatField, DateTimeField, UUIDField

import datetime

DATABASE_NAME = 'golem.db'
START_BUDGET = 42000000

db = SqliteDatabase( DATABASE_NAME, threadlocals=True)

class Database:
    def __init__( self ):
        self.db = db
        self.name = DATABASE_NAME

        db.connect()
        if not Node.table_exists():
            Node.create_table()
        if not Bank.table_exists():
            Bank.create_table()

    def createDatabase(self):
        db.create_tables([Node, Bank])

    def checkNode(self, nodeId ):
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

class Bank( BaseModel ):
    nodeId = ForeignKeyField( Node, related_name='has', unique=True )
    val = FloatField( default = START_BUDGET )
    created_date = DateTimeField( default = datetime.datetime.now )
