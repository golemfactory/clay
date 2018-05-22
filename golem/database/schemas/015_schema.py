import peewee as pw

SCHEMA_VERSION = 15


def migrate(migrator, *_, **__):
    """Write your migrations here."""

    migrator.drop_index('hardwarepreset', 'name')

    migrator.add_index('hardwarepreset', 'name', unique=True)

    migrator.add_fields(
        'performance',

        min_accepted=pw.FloatField(default=0.0))

    migrator.drop_index('performance', 'environment_id')

    migrator.add_index('performance', 'environment_id', unique=True)


def rollback(migrator, *_, **__):
    """Write your rollback migrations here."""

    migrator.remove_fields('performance', 'min_accepted')

    migrator.drop_index('performance', 'environment_id')

    migrator.add_index('performance', 'environment_id', unique=True)

    migrator.drop_index('hardwarepreset', 'name')

    migrator.add_index('hardwarepreset', 'name', unique=True)

    migrator.remove_model('basemodel')
