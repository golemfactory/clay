import inspect
import sys
from contextlib import contextmanager
from typing import Optional

import os
import peewee
from peewee_migrate import Router as _Router

import golem
from golem.core.simpleenv import get_local_datadir
from golem.database import Database
from golem.database.migration import default_migrate_dir
from golem.model import DB_MODELS, db

TEMPLATE = """SCHEMA_VERSION = {schema_version}
from {model_package} import *  # pylint: disable=unused-import

{template}
"""


def latest_migration_exists():
    environment = Router.Environment(default_migrate_dir())
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
            return

    print('> database:   {}'.format(database.db.database))
    print('> output dir: {}'.format(migrate_dir))

    try:
        with _patch_peewee():
            r = Router(database.db, migrate_dir,
                       database.SCHEMA_VERSION, template)
            name = r.create(migration_name, auto=golem.model)
    finally:
        database.close()
        if os.path.exists('peewee.db'):
            os.unlink('peewee.db')

    partial_path = os.path.join(migrate_dir, name)
    return '{}.py'.format(partial_path)


class Router(_Router):

    class Environment:

        def __init__(self, migrate_dir=default_migrate_dir()):
            self._router = Router.__new__(Router)
            self._router.migrate_dir = migrate_dir
            self._router._schema_version = None
            self._router._template = None

        @property
        def scripts(self):
            return self._router.todo

        @property
        def last_version(self):
            files = self.scripts
            if files:
                return self.version_from_name(files[-1])

        @property
        def last_script(self):
            files = self.scripts
            return '{}.py'.format(files[-1]) if files else None

        @staticmethod
        def version_from_name(file_name):
            if not file_name:
                return None

            split = file_name.split('_')
            return int(split[0])

    def __init__(self,
                 database: peewee.Database,
                 migrate_dir: str,
                 schema_version: int,
                 template: str,
                 **kwargs):

        super().__init__(database, migrate_dir, **kwargs)
        self._schema_version = schema_version
        self._template = template

    def next_schema_num(self):
        todo = self.todo
        if not todo:
            return self._schema_version

        version = self.Environment.version_from_name(todo[-1])
        if version:
            return version + 1

    def compile(self, name, migrate='', rollback='', _num=None):
        name = '{:03}_{}'.format(self.next_schema_num(), name)
        filename = name + '.py'
        path = os.path.join(self.migrate_dir, filename)

        with open(path, 'w') as f:
            params = dict(migrate=migrate, rollback=rollback, name=filename)
            formatted = self._template.format(**params)
            f.write(formatted)

        return name


@contextmanager
def _patch_peewee():
    """
    Temporarily assign all known models and field types to the peewee module.
    peewee_migrate assumes that all models and field types are located there.
    """

    def is_field(cls):
        return inspect.isclass(cls) and issubclass(cls, peewee.Field)

    db_fields = [c for _, c in inspect.getmembers(golem.model, is_field)]

    undo = set()

    for db_class in db_fields + DB_MODELS:
        property_name = db_class.__name__

        if not hasattr(peewee, property_name):
            undo.add(property_name)
            setattr(peewee, property_name, db_class)

    yield

    for property_name in undo:
        delattr(peewee, property_name)


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
            'nargs': '+',
            'type': str,
            'default': None,
            'help': 'Golem\'s datadir'
        },
        'outdir': {
            'nargs': '+',
            'type': str,
            'default': None,
            'help': 'Destination dir to save migrations to'
        },
        'name': {
            'nargs': '+',
            'type': str,
            'default': None,
            'help': 'Migration name'
        },
        'force': {
            'action': 'store_true',
            'type': bool,
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
    data_dir = parsed.datadir
    out_dir = parsed.outdir
    name = parsed.name
    force = parsed.force

    create_migration(data_dir, out_dir, name, force)


if __name__ == '__main__':
    create_from_commandline(sys.argv[1:])
