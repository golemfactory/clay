# pylint: disable=unused-argument
import golem
import peewee as pw

SCHEMA_VERSION = 15


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'performance',
        golem_version=pw.CharField(default=golem.__version__, max_length=255)
    )

    migrator.drop_index('performance', 'environment_id')

    migrator.add_index('performance', 'environment_id', 'golem_version',
                       unique=True)


def rollback(migrator, database, fake=False, **kwargs):
    migrator.drop_index('performance', 'environment_id', 'golem_version')

    migrator.add_index('performance', 'environment_id', unique=True)

    migrator.remove_fields('performance', 'golem_version')
