import inspect
import sys
from contextlib import contextmanager
from typing import Optional

import os
import peewee
from peewee_migrate import Router

import golem
from golem.core.simpleenv import get_local_datadir
from golem.database import Database, schemas
from golem.model import DB_MODELS, db

TEMPLATE = """SCHEMA_VERSION = {schema_version}
from {model_package} import *  # pylint: disable=unused-import

{template}
"""


def create_migration(data_dir: Optional[str] = None,
                     out_dir: Optional[str] = None,
                     migration_name: Optional[str] = None):

    """ Create a schema migration script """
    from peewee_migrate import router

    if not data_dir:
        data_dir = get_local_datadir('default')
    if not out_dir:
        out_dir = schemas.__path__[0]
    if not migration_name:
        migration_name = 'schema'

    database = Database(db, data_dir, DB_MODELS, migrate=False)
    template = TEMPLATE.format(schema_version=database.SCHEMA_VERSION,
                               model_package=golem.model.__name__,
                               template=router.MIGRATE_TEMPLATE)

    last_version = last_schema_version(database.db, out_dir)
    if database.SCHEMA_VERSION <= (last_version or 0):
        print('Database schema migration scripts are up-to-date')
        return

    print('> database:   {}'.format(database.db.database))
    print('> output dir: {}'.format(out_dir))

    try:
        with _patch_peewee():
            r = _Router(database.db, out_dir, database.SCHEMA_VERSION, template)
            name = r.create(migration_name, auto=golem.model)
    finally:
        database.close()
        if os.path.exists('peewee.db'):
            os.unlink('peewee.db')

    partial_path = os.path.join(out_dir, name)
    return '{}.py'.format(partial_path)


def last_schema_version(database, out_dir):
    router = _Router(database, out_dir, None, None)
    version = router.next_schema_num()
    return version - 1 if version else None


class _Router(Router):

    def __init__(self, database, out_dir, schema_version, template, **kwargs):
        super().__init__(database, out_dir, **kwargs)
        self._schema_version = schema_version
        self._template = template

    def next_schema_num(self):
        todo = self.todo
        if not todo:
            return self._schema_version

        split = todo[-1].split('_')
        return int(split[0]) + 1

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

    create_migration(data_dir, out_dir, name)


if __name__ == '__main__':
    create_from_commandline(sys.argv[1:])
