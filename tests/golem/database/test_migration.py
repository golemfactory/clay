from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import patch

import os
from peewee import CharField
from peewee_migrate.migrator import SchemaMigrator, Migrator
from playhouse.migrate import migrate

import golem
from golem.database import Database
from golem.database.migration.create import create_from_commandline, \
    create_migration
from golem.database.migration.migrate import migrate_schema
from golem.model import Account, BaseModel, DB_MODELS, Stats
from golem.testutils import DatabaseFixture, TempDirFixture


@patch('golem.database.migration.create.create_migration')
class TestMigrationCommandLine(TestCase):

    def test_empty(self, create):
        commandline_args = []
        create_from_commandline(commandline_args)
        create.assert_called_with(None, None, None, False)

    def test_short_flags(self, create):
        commandline_args = ['-n', 'custom_name',
                            '-d', 'custom_data_dir',
                            '-o', 'custom_out_dir',
                            '-f']

        create_from_commandline(commandline_args)
        create.assert_called_with(
            'custom_data_dir',
            'custom_out_dir',
            'custom_name',
            True
        )

    def test_long_flags(self, create):
        commandline_args = ['--name', 'custom_name',
                            '--datadir', 'custom_data_dir',
                            '--outdir', 'custom_out_dir',
                            '--force']

        create_from_commandline(commandline_args)
        create.assert_called_with(
            'custom_data_dir',
            'custom_out_dir',
            'custom_name',
            True
        )


class TestCreateMigration(TempDirFixture):

    @patch('golem.database.migration.create.get_local_datadir')
    @patch('golem.database.migration.create.default_migrate_dir')
    def test_create_params(self, default_migrate_dir, get_local_datadir):
        out_dir = os.path.join(self.tempdir, 'schemas')
        os.makedirs(out_dir, exist_ok=True)

        default_migrate_dir.return_value = out_dir
        get_local_datadir.return_value = self.tempdir

        output_file = create_migration()

        assert len(os.listdir(out_dir)) == 1
        assert os.path.exists(output_file)
        assert output_file == os.path.join(
            out_dir, '{:03}_schema.py'.format(Database.SCHEMA_VERSION)
        )

    def test_create_custom_params(self):
        sub_dir = os.path.join(self.tempdir, 'subdirectory')
        out_dir = os.path.join(sub_dir, 'schemas')
        data_dir = self.tempdir
        name = 'test_name'

        os.makedirs(out_dir, exist_ok=True)

        output_file = create_migration(data_dir, out_dir, name)

        assert len(os.listdir(out_dir)) == 1
        assert os.path.exists(output_file)
        assert output_file == os.path.join(
            out_dir, '{:03}_{}.py'.format(Database.SCHEMA_VERSION, name)
        )

        create_migration(data_dir, out_dir, name)
        assert len(os.listdir(out_dir)) == 1
        assert os.path.exists(output_file)

        create_migration(data_dir, out_dir, name, force=True)
        assert len(os.listdir(out_dir)) == 1
        assert os.path.exists(output_file)


class ExtraTestModel(BaseModel):
    value = CharField()


class SecondExtraTestModel(BaseModel):
    value = CharField()


def create_db_data():
    Account.create(node_id='first_node')
    Account.create(node_id='second_node')
    Stats.create(name='stats', value=1)


def collect_all_db_data(models):
    return {m: set(m.select().execute()) for m in models}


def unregister_extra_models():
    if hasattr(golem.model, 'ExtraTestModel'):
        delattr(golem.model, 'ExtraTestModel')
    if hasattr(golem.model, 'SecondExtraTestModel'):
        delattr(golem.model, 'SecondExtraTestModel')

    if ExtraTestModel in golem.model.DB_MODELS:
        golem.model.DB_MODELS.remove(ExtraTestModel)
    if SecondExtraTestModel in golem.model.DB_MODELS:
        golem.model.DB_MODELS.remove(SecondExtraTestModel)


@contextmanager
def schema_version_ctx(*cleanup_fns):
    initial_version = Database.SCHEMA_VERSION
    yield
    Database.SCHEMA_VERSION = initial_version

    for cleanup_fn in cleanup_fns or []:
        cleanup_fn()


class TestMigrationUpgradeDowngrade(DatabaseFixture):

    def test_upgrade_twice(self):

        data_dir = self.tempdir
        out_dir = os.path.join(data_dir, 'schemas')
        initial_db_models = list(DB_MODELS)

        # -- Populate the database (0)
        create_db_data()

        # -- Create a schema snapshot (0)
        create_migration(data_dir, out_dir)
        assert len(os.listdir(out_dir)) == 1

        # -- Store initial state of the database (0)
        initial_state = collect_all_db_data(DB_MODELS)
        assert len(initial_state[Account]) == 2
        assert len(initial_state[Stats]) == 1

        from_version = Database.SCHEMA_VERSION

        with schema_version_ctx(unregister_extra_models):

            # -- Add a model and bump version (1)
            golem.model.ExtraTestModel = ExtraTestModel
            golem.model.DB_MODELS.insert(0, ExtraTestModel)
            Database.SCHEMA_VERSION = from_version + 1

            ExtraTestModel.create_table()

            # -- Create a new migration file (1)
            create_migration(data_dir, out_dir)
            assert len(os.listdir(out_dir)) == 2

            # -- Add a second model, alter other and bump version (2)
            golem.model.SecondExtraTestModel = SecondExtraTestModel
            golem.model.DB_MODELS.insert(0, SecondExtraTestModel)
            Database.SCHEMA_VERSION = from_version + 2

            SecondExtraTestModel.create_table()

            # -- Create a new migration file (2)
            create_migration(data_dir, out_dir)
            assert len(os.listdir(out_dir)) == 3

            # -- Drop the model table, downgrade version (0)
            Database.SCHEMA_VERSION = from_version
            ExtraTestModel.drop_table()
            SecondExtraTestModel.drop_table()

            assert not ExtraTestModel.table_exists()
            assert not SecondExtraTestModel.table_exists()

            # -- Migrate to newer version (2)
            migrate_schema(self.database, from_version, from_version + 2,
                           migrate_dir=out_dir)

            # -- Assert that migration was successful (2)
            assert ExtraTestModel.table_exists()
            assert SecondExtraTestModel.table_exists()

            current_state = collect_all_db_data(DB_MODELS)
            assert self.database.get_user_version() == from_version + 2
            assert len(current_state) == len(initial_state) + 2

            # -- Test migration (2)
            ExtraTestModel.create(value='extra value')
            SecondExtraTestModel.create(value='second extra value')

            # -- Downgrade database (0)
            migrate_schema(self.database, from_version + 2, from_version,
                           migrate_dir=out_dir)

            # -- Assert that state matches the initial state (0)
            assert not ExtraTestModel.table_exists()
            assert not SecondExtraTestModel.table_exists()

            current_state = collect_all_db_data(initial_db_models)
            assert self.database.get_user_version() == from_version
            assert current_state == initial_state


class TestMigrationAlteredModel(DatabaseFixture):

    def test_add_remove_property(self):

        data_dir = self.tempdir
        out_dir = os.path.join(data_dir, 'schemas')

        # -- Create some Account models
        create_db_data()

        # -- Snapshot
        create_migration(data_dir, out_dir)
        assert len(os.listdir(out_dir)) == 1

        extra_field = CharField(default='default', null=False)
        from_version = Database.SCHEMA_VERSION

        with schema_version_ctx(lambda: Account._meta.
                                remove_field('extra_field')):

            # -- Add an extra field, increase version
            Database.SCHEMA_VERSION = from_version + 1
            extra_field.add_to_class(Account, 'extra_field')

            # -- Take a snapshot
            create_migration(data_dir, out_dir)
            assert len(os.listdir(out_dir)) == 2

            # -- Revert changes to initial state
            Database.SCHEMA_VERSION = from_version

            # -- Upgrade
            migrate_schema(self.database, from_version, from_version + 1,
                           migrate_dir=out_dir)
            account_columns = self.database.db.get_columns('account')
            assert any(column.name == 'extra_field'
                       for column in account_columns)

            # -- Downgrade
            Account._meta.remove_field('extra_field')
            del Account.extra_field

            migrate_schema(self.database, from_version + 1, from_version,
                           migrate_dir=out_dir)

            account_columns = self.database.db.get_columns('account')
            assert all(column.name != 'extra_field'
                       for column in account_columns)
