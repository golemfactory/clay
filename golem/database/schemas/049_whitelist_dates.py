# pylint: disable=no-member
# pylint: disable=unused-argument
import logging

from golem.model import UTCDateTimeField, default_now

SCHEMA_VERSION = 49


logger = logging.getLogger('golem.database')


def migrate(migrator, database, fake=False, **kwargs):
    # Migration 026 forgot to add these 2 fields
    # Checking for existance since some nodes mysteriously have them
    docker_table = 'dockerwhitelist'
    column_names = [x.name for x in database.get_columns(docker_table)]
    if 'created_date' in column_names:
        logger.info('created_date already exist. skipping migration')
        return
    migrator.add_fields(
        docker_table,
        created_date=UTCDateTimeField(default=default_now),
        modified_date=UTCDateTimeField(default=default_now),
    )


def rollback(migrator, database, fake=False, **kwargs):
    # no removing of fields since they should have been there from 026
    pass
