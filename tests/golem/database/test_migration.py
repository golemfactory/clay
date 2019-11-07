# pylint: disable=protected-access
import datetime
import functools
from contextlib import contextmanager
import typing
from unittest import TestCase
from unittest.mock import patch
import uuid

import os

from peewee import CharField

import golem
from golem.database import Database
from golem.database.migration import default_migrate_dir
from golem.database.migration.router import Router
from golem.database.migration.create import create_from_commandline, \
    create_migration
from golem.database.migration.migrate import migrate_schema, choose_scripts
from golem.model import Account, BaseModel, DB_MODELS, Stats, DB_FIELDS
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

    def test_create_params(self):
        out_dir = os.path.join(self.tempdir, 'schemas')
        os.makedirs(out_dir, exist_ok=True)

        output_file = create_migration(data_dir=self.tempdir,
                                       migrate_dir=out_dir)

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
        create_migration(data_dir, out_dir, migration_name='test_0_init')
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
            create_migration(data_dir, out_dir, migration_name='test_1_ETM')
            assert len(os.listdir(out_dir)) == 2

            # -- Add a second model, alter other and bump version (2)
            golem.model.SecondExtraTestModel = SecondExtraTestModel
            golem.model.DB_MODELS.insert(0, SecondExtraTestModel)
            Database.SCHEMA_VERSION = from_version + 2

            SecondExtraTestModel.create_table()

            # -- Create a new migration file (2)
            create_migration(data_dir, out_dir, migration_name='test_2_SETM')
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


class TestSavedMigrations(TempDirFixture):

    @contextmanager
    def database_context(self):
        from golem.model import db
        version = Database.SCHEMA_VERSION
        database = Database(db, fields=DB_FIELDS, models=DB_MODELS,
                            db_dir=self.tempdir, schemas_dir=None)
        database.schemas_dir = default_migrate_dir()
        yield database
        Database.SCHEMA_VERSION = version
        database.close()

    @patch('golem.database.Database._create_tables')
    def test_invalid(self, create_db):
        with self.database_context() as database:
            create_db.reset_mock()
            assert all(not m.table_exists() for m in DB_MODELS)

            database._migrate_schema(0, Database.SCHEMA_VERSION)
            assert create_db.called

    @patch('golem.database.Database._create_tables')
    def test_all(self, _):
        with self.database_context() as database:
            assert all(not m.table_exists() for m in DB_MODELS)

            database._migrate_schema(6, 10)
            assert database.get_user_version() == 10
            database._migrate_schema(10, Database.SCHEMA_VERSION)
            assert database.get_user_version() == Database.SCHEMA_VERSION

            assert all(m.table_exists() for m in DB_MODELS)

    def test_same_version(self):
        with self.database_context() as database:
            database._migrate_schema(Database.SCHEMA_VERSION,
                                     Database.SCHEMA_VERSION)
            assert all(m.table_exists() for m in DB_MODELS)

    @patch('golem.database.Database._create_tables')
    def test_18(self, _create_tables_mock):
        with self.database_context() as database:
            database._migrate_schema(6, 17)
            sender_node = 'adbeef' + 'deadbeef' * 15
            subtask_id = str(uuid.uuid4())
            database.db.execute_sql(
                "INSERT INTO income ("
                "sender_node, subtask, value, created_date, modified_date,"
                " overdue"
                ")"
                f" VALUES (?, ?, 10, datetime('now'),"
                "           datetime('now'), 0)",
                (
                    sender_node,
                    subtask_id,
                ),
            )
            database._migrate_schema(17, 18)
            cursor = database.db.execute_sql(
                "SELECT payer_address FROM income"
                f" WHERE sender_node = ? AND subtask = ?"
                " LIMIT 1",
                (
                    sender_node,
                    subtask_id,
                ),
            )
            value = cursor.fetchone()[0]
            self.assertEqual(value, 'c106A6f2534E74b9D5890d13C5991A3fB146Ae52')

    @patch('golem.database.Database._create_tables')
    def test_20_income_value_received(self, _create_tables_mock):
        with self.database_context() as database:
            database._migrate_schema(6, 19)
            database.db.execute_sql(
                "INSERT INTO income ("
                "sender_node, subtask, value, created_date, modified_date,"
                " overdue, payer_address, \"transaction\")"
                " VALUES ('0xdead', '0xdead', 10, datetime('now'),"
                "         datetime('now'), 0,"
                "         '0eeA941c1244ADC31F53525D0eC1397ff6951C9C',"
                "         'transid')"
            )
            database._migrate_schema(19, 20)
            cursor = database.db.execute_sql(
                "SELECT value_received FROM income"
                " WHERE sender_node = '0xdead' AND subtask = '0xdead'"
                " LIMIT 1"
            )
            value = cursor.fetchone()[0]
            self.assertEqual(value, '10')

    @patch('golem.database.Database._create_tables')
    def test_30_wallet_operation_alter(self, _create_tables_mock):
        tx_hash = (
            '0x8f30cb104c188f612f3492f53c069f65a4c4e2a8d4432a4878b1fd33f36787d3'
        )
        with self.database_context() as database:
            database._migrate_schema(6, 29)
            cursor = database.db.execute_sql(
                "INSERT INTO walletoperation"
                " (tx_hash, direction, operation_type, status,"
                "  sender_address, recipient_address, gas_cost,"
                "  amount, currency, created_date, modified_date)"
                " VALUES"
                " (?, 'outgoing', 'task_payment', 'awaiting',"
                "  '', '', 0,"
                "  1, 'GNT', datetime('now'), datetime('now'))",
                (
                    tx_hash,
                )
            )
            wallet_operation_id = cursor.lastrowid
            # Migration used to fail because of foreign key and
            # sqlite inability to DROP NOT NULL
            cursor.execute(
                "INSERT INTO taskpayment"
                " (wallet_operation_id, node, task, subtask,"
                "  accepted_ts, settled_ts,"
                "  expected_amount, created_date, modified_date)"
                " VALUES"
                " (?, '', '', '',"
                "  datetime('now'), datetime('now'),"
                "  1, datetime('now'), datetime('now'))",
                (
                    wallet_operation_id,
                )
            )
            database._migrate_schema(29, 30)
            cursor = database.db.execute_sql(
                "SELECT tx_hash FROM walletoperation"
                " LIMIT 1"
            )
            value = cursor.fetchone()[0]
            self.assertEqual(value, tx_hash)

    @patch('golem.database.Database._create_tables')
    def test_31_payments_migration(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 30)

            details = '{"node_info": {"node_name": "Laughing Octopus", "key": "392e54805752937326aa87da97a69c9271f7b4423382fb2563a349d54c44d9a904f38b4f2e3a022572c8257220426d8e5e34198be2cc8971bc149f1a368161e3", "prv_port": 40201, "pub_port": 40201, "p2p_prv_port": 40200, "p2p_pub_port": 40200, "prv_addr": "10.30.8.12", "pub_addr": "194.181.80.91", "prv_addresses": ["10.30.8.12", "172.17.0.1"], "hyperdrive_prv_port": 3282, "hyperdrive_pub_port": 3282, "port_statuses": {"3282": "timeout", "40200": "timeout", "40201": "timeout"}, "nat_type": "Symmetric NAT"}, "fee": 116264444444444, "block_hash": "184575de00b91fdac0ccd1c763d5b56b967898e3a541f400480b01a6dbf1fef9", "block_number": 1937551, "check": null, "tx": "4b9f628f16c82d0fe3f3ab144feef7940a0093107d521b45a8a0bfb5739400be"}'  # noqa pylint: disable=line-too-long
            database.db.execute_sql(
                "INSERT INTO payment ("
                "    subtask, created_date, modified_date, status,"
                "    payee, value, details)"
                " VALUES ('0xdead', datetime('now'), datetime('now'), 1,"
                "         '0x0eeA941c1244ADC31F53525D0eC1397ff6951C9C', 10,"
                f"        '{details}')"
            )
            database._migrate_schema(30, 31)

            # UNIONS don't work here. Do it manually
            cursor = database.db.execute_sql("SELECT count(*) FROM payment")
            payment_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql(
                "SELECT count(*) FROM walletoperation",
            )
            wo_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql("SELECT count(*) FROM taskpayment")
            tp_count = cursor.fetchone()[0]
            # Migrated payments shouldn't be removed
            self.assertEqual(payment_count, 1)
            self.assertEqual(wo_count, 1)
            self.assertEqual(tp_count, 1)

    @patch('golem.database.Database._create_tables')
    def test_31_payments_migration_invalid_node_info(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 30)

            details_null_key = '{"node_info": {"key": null}}'
            details_null_node = '{"node_info": null}'
            for cnt, details in enumerate(
                    (details_null_key, details_null_node),
            ):
                database.db.execute_sql(
                    "INSERT INTO payment ("
                    "    subtask, created_date, modified_date, status,"
                    "    payee, value, details)"
                    " VALUES (?, datetime('now'), datetime('now'), 1,"
                    "         '0x0eeA941c1244ADC31F53525D0eC1397ff6951C9C', 10,"
                    "         ?)",
                    (f"0xdead{cnt}", details, ),
                )
            database._migrate_schema(30, 31)

            # UNIONS don't work here. Do it manually
            cursor = database.db.execute_sql("SELECT count(*) FROM payment")
            payment_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql(
                "SELECT count(*) FROM walletoperation",
            )
            wo_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql("SELECT count(*) FROM taskpayment")
            tp_count = cursor.fetchone()[0]
            # Migrated payments shouldn't be removed
            self.assertEqual(payment_count, 2)
            self.assertEqual(wo_count, 0)
            self.assertEqual(tp_count, 0)

    @patch('golem.database.Database._create_tables')
    def test_32_incomes_migration(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 31)

            database.db.execute_sql(
                "INSERT INTO income ("
                "    subtask, sender_node, created_date, modified_date,"
                "    overdue,"
                "    payer_address, value_received, value)"
                " VALUES ('0xdead', '0xdead', datetime('now'), datetime('now'),"
                "         1,"
                "         '0x0eeA941c1244ADC31F53525D0eC1397ff6951C9C',"
                "         '1', '2')"
            )
            database._migrate_schema(31, 32)

            # UNIONS don't work here. Do it manually
            cursor = database.db.execute_sql("SELECT count(*) FROM income")
            income_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql(
                "SELECT count(*) FROM walletoperation",
            )
            wo_count = cursor.fetchone()[0]
            cursor = database.db.execute_sql("SELECT count(*) FROM taskpayment")
            tp_count = cursor.fetchone()[0]
            # Migrated incomes shouldn't be removed
            self.assertEqual(income_count, 1)
            self.assertEqual(wo_count, 1)
            self.assertEqual(tp_count, 1)

    @patch('golem.database.Database._create_tables')
    def test_33_deposit_payments_migration(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 32)

            tx_hash = (
                '0xc9d936c0c1a10f19ab2952ccb4901a1118ea9a'
                '4f78379ee2ebaa7f9e7beb1eb5'
            )
            value = 'af7a173aa545c72'
            status = 2  # sent
            fee = 'af7a173aa545c71'

            database.db.execute_sql(
                "INSERT INTO depositpayment ("
                "    tx, value, status, fee,"
                "    created_date, modified_date)"
                " VALUES (?, ?, ?, ?,"
                "    datetime('now'), datetime('now'))",
                (
                    tx_hash, value, status, fee,
                )
            )
            database._migrate_schema(32, 33)

            cursor = database.db.execute_sql(
                "SELECT count(*) FROM walletoperation",
            )
            wo_count = cursor.fetchone()[0]
            self.assertEqual(wo_count, 1)
            cursor.execute(
                'SELECT tx_hash, status, amount, gas_cost FROM walletoperation',
            )
            self.assertCountEqual(
                cursor.fetchone(),
                [
                    tx_hash,
                    'sent',
                    value,
                    fee,
                ],
            )

    @patch('golem.database.Database._create_tables')
    def test_33_deposit_payments_migration_table_missing(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 32)

            database.db.RETRY_TIMEOUT = datetime.timedelta(seconds=0)
            database.db.execute_sql(
                "DROP TABLE depositpayment"
            )
            database._migrate_schema(32, 33)

            cursor = database.db.execute_sql(
                "SELECT count(*) FROM walletoperation",
            )
            wo_count = cursor.fetchone()[0]
            self.assertEqual(wo_count, 0)

    @patch('golem.database.Database._create_tables')
    def test_36_charged_from_deposit(self, *_args):
        with self.database_context() as database:
            database._migrate_schema(6, 35)
            database.db.RETRY_TIMEOUT = datetime.timedelta(seconds=0)
            database._migrate_schema(35, 36)


class TestDuplicateMigrations(DatabaseFixture):

    def test_no_duplicate_migrations(self):
        router = Router(
            database=self.database.db,
            migrate_dir=default_migrate_dir(),
            schema_version=Database.SCHEMA_VERSION)
        migration_script_names: typing.List[str] = router.environment.scripts
        version_to_name: typing.Dict[str, str] = {}

        for name in migration_script_names:
            split = name.split('_', 1)
            version = split[0]

            if version_to_name.get(version):
                self.fail(f"Migration scripts must have unique version numbers."
                          f" Colliding file names: {name}, "
                          f"{version + '_' + version_to_name[version]}")

            version_to_name[version] = split[1]


def generate(start, stop):
    return ['{:03}_script'.format(i) for i in range(start, stop + 1)]


def choose(scripts, start, stop):
    return choose_scripts(scripts, start, stop)[0]


class TestChooseMigrationScripts(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.scripts = generate(0, 30)

    def test(self):
        get = functools.partial(choose, self.scripts)

        assert get(-10, -10) == []
        assert get(-10, -2) == []
        assert get(-10, 0) == []
        assert get(1, 10) == generate(2, 10)
        assert get(7, 12) == generate(8, 12)
        assert get(1, 40) == generate(2, 30)
        assert get(7, 12) == generate(8, 12)
        assert get(29, 40) == generate(30, 30)
        assert get(40, 40) == []
        assert get(41, 42) == []

    def test_downgrade(self):
        get = functools.partial(choose, self.scripts)

        def gen_rev(s, e):
            return generate(s, e)[::-1]

        assert get(-10, -10) == []
        assert get(-10, -2) == []
        assert get(-10, 0) == []
        assert get(10, 1) == gen_rev(2, 10)
        assert get(12, 7) == gen_rev(8, 12)
        assert get(40, 1) == gen_rev(2, 30)
        assert get(12, 7) == gen_rev(8, 12)
        assert get(40, 29) == gen_rev(30, 30)
        assert get(40, 40) == []
        assert get(42, 41) == []
