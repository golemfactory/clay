import sys
from typing import Optional

import os

import golem
from golem.core.simpleenv import get_local_datadir
from golem.database import Database
from golem.database.migration import default_migrate_dir, patch_peewee
from golem.database.migration.router import Router
from golem.model import DB_MODELS, db

TEMPLATE = """# pylint: disable=no-member
# pylint: disable=too-few-public-methods
SCHEMA_VERSION = {schema_version}
from {model_package} import *  # pylint: disable=unused-import

{template}
"""


def latest_migration_exists(migrate_dir=default_migrate_dir()):
    environment = Router.Environment(migrate_dir)
    return environment.last_version == Database.SCHEMA_VERSION


def create_migration(data_dir: Optional[str] = None,
                     migrate_dir: Optional[str] = None,
                     migration_name: Optional[str] = None,
                     force: bool = False):

    """ Create a schema migration script """
    from peewee_migrate.router import MIGRATE_TEMPLATE

    if not data_dir:
        data_dir = get_local_datadir('default')
    if not migrate_dir:
        migrate_dir = default_migrate_dir()
    if not migration_name:
        migration_name = 'schema'

    environment = Router.Environment(migrate_dir)
    database = Database(db, data_dir, DB_MODELS, migrate=False)
    template = TEMPLATE.format(schema_version=database.SCHEMA_VERSION,
                               model_package=golem.model.__name__,
                               template=MIGRATE_TEMPLATE)

    if database.SCHEMA_VERSION <= (environment.last_version or 0):
        if force:
            script_path = os.path.join(migrate_dir, environment.last_script)
            os.unlink(script_path)
        else:
            print('Migration scripts are up-to-date')
            return None

    print('> database:   {}'.format(database.db.database))
    print('> output dir: {}'.format(migrate_dir))

    try:
        with patch_peewee():
            r = Router(database.db, migrate_dir,
                       database.SCHEMA_VERSION, template)
            name = r.create(migration_name, auto=golem.model)
    finally:
        database.close()
        if os.path.exists('peewee.db'):
            os.unlink('peewee.db')

    partial_path = os.path.join(migrate_dir, name)
    return '{}.py'.format(partial_path)


def _parse_commandline_args(args) -> tuple:
    import argparse

    flags = [
        ('name', ('-n', '--name',)),
        ('datadir', ('-d', '--datadir')),
        ('outdir', ('-o', '--outdir',)),
        ('force', ('-f', '--force'))
    ]

    flag_options = {
        'datadir': {
            'nargs': 1,
            'type': str,
            'default': None,
            'help': 'Golem\'s datadir'
        },
        'outdir': {
            'nargs': 1,
            'type': str,
            'default': None,
            'help': 'Destination dir to save migrations to'
        },
        'name': {
            'nargs': 1,
            'type': str,
            'default': None,
            'help': 'Migration name'
        },
        'force': {
            'action': 'store_true',
            'default': False,
            'help': 'Recreate the migration script for current schema'
        }
    }

    parser = argparse.ArgumentParser(
        prog='Database schema migration creator',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    for flag_name, flag in flags:
        parser.add_argument(*flag, **flag_options[flag_name])
    return parser.parse_known_args(args)


def create_from_commandline(args):
    """ Parse command line arguments and create a schema migration script """
    parsed, _ = _parse_commandline_args(args)
    data_dir = parsed.datadir[0] if parsed.datadir else None
    out_dir = parsed.outdir[0] if parsed.outdir else None
    name = parsed.name[0] if parsed.name else None
    force = parsed.force

    create_migration(data_dir, out_dir, name, force)


if __name__ == '__main__':
    create_from_commandline(sys.argv[1:])
