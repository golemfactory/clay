import peewee as pw

SCHEMA_VERSION = 15


def migrate(migrator, *_, **__):
    migrator.add_fields('performance', min_accepted=pw.FloatField(default=0.0))


def rollback(migrator, *_, **__):
    migrator.remove_fields('performance', 'min_accepted')
