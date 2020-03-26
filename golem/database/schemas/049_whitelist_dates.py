# pylint: disable=no-member
# pylint: disable=unused-argument

from golem.model import UTCDateTimeField, default_now

SCHEMA_VERSION = 49


def migrate(migrator, database, fake=False, **kwargs):
    migrator.add_fields(
        'dockerwhitelist',
        created_date=UTCDateTimeField(default=default_now),
        modified_date=UTCDateTimeField(default=default_now),
    )


def rollback(migrator, database, fake=False, **kwargs):
    migrator.remove_fields('dockerwhitelist', 'created_date', 'modified_date')
