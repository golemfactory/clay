import os
import peewee
from peewee_migrate import Router as _Router

from golem.database.migration import default_migrate_dir


class Router(_Router):

    class Environment:

        def __init__(self, migrate_dir: str = default_migrate_dir()):
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
        def version_from_name(file_name: str):
            if not file_name:
                return None

            split = file_name.split('_', 1)
            return int(split[0])

    def __init__(self,
                 database: peewee.Database,
                 migrate_dir: str,
                 schema_version: int,
                 template: str = None,
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

    def compile(self, name: str, migrate: str = '', rollback: str = '', _=None):
        name = '{:03}_{}'.format(self.next_schema_num(), name)
        filename = name + '.py'
        path = os.path.join(self.migrate_dir, filename)

        with open(path, 'w') as f:
            params = dict(migrate=migrate, rollback=rollback, name=filename)
            formatted = self._template.format(**params)
            f.write(formatted)

        return name
