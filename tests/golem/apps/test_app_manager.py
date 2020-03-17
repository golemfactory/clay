from mock import Mock, patch

from golem.apps.manager import AppManager
from golem.apps import (
    AppDefinition,
    load_app_from_json_file,
    load_apps_from_dir,
)
from golem.testutils import TempDirFixture, DatabaseFixture

ROOT_PATH = 'golem.apps.manager'
APP_DEF = AppDefinition(
    name='test_app',
    requestor_env='test_env',
    requestor_prereq={
        'key1': 'value',
        'key2': [1, 2, 3]
    },
    max_benchmark_score=1.0
)
APP_ID = APP_DEF.id


class AppManagerTestBase(DatabaseFixture):

    def setUp(self):
        super().setUp()
        app_path = self.new_path / 'apps'
        app_path.mkdir(exist_ok=True)
        self.app_manager = AppManager(app_path, False)


class TestUpdateApps(AppManagerTestBase):

    @patch(f'{ROOT_PATH}.download_definitions')
    @patch(f'{ROOT_PATH}.EventPublisher')
    def test_update(self, publisher_mock, download_mock):
        download_mock.return_value = [APP_DEF]
        self.app_manager.update_apps()
        self.assertEqual(self.app_manager.apps(), [(APP_ID, APP_DEF)])
        self.assertEqual(self.app_manager.app(APP_ID), APP_DEF)
        self.assertFalse(self.app_manager.enabled(APP_ID))
        self.assertEqual(publisher_mock.publish.call_count, 1)

        # Definition already exists locally
        download_mock.return_value = []
        self.app_manager.update_apps()
        self.assertEqual(self.app_manager.apps(), [(APP_ID, APP_DEF)])
        self.assertEqual(publisher_mock.publish.call_count, 1)


class TestRegisterApp(AppManagerTestBase):

    def test_register_app(self):
        self.app_manager.register_app(APP_DEF)
        self.assertEqual(self.app_manager.apps(), [(APP_ID, APP_DEF)])
        self.assertEqual(self.app_manager.app(APP_ID), APP_DEF)
        self.assertFalse(self.app_manager.enabled(APP_ID))

    def test_re_register(self):
        self.app_manager.register_app(APP_DEF)
        with self.assertRaises(ValueError):
            self.app_manager.register_app(APP_DEF)

    def test_delete_app(self):
        self.app_manager.register_app(APP_DEF)
        self.app_manager._app_file_names[APP_ID] = mocked_file = Mock()
        mocked_file.unlink = Mock()
        self.assertEqual(self.app_manager.apps(), [(APP_ID, APP_DEF)])
        self.app_manager.delete(APP_ID)
        self.assertEqual(self.app_manager.apps(), [])
        mocked_file.unlink.assert_called_once_with()


class TestSetEnabled(AppManagerTestBase):

    def test_app_not_registered(self):
        with self.assertRaises(ValueError):
            self.app_manager.set_enabled(APP_ID, True)

    def test_enable_disable(self):
        self.app_manager.register_app(APP_DEF)
        self.assertFalse(self.app_manager.enabled(APP_ID))
        self.app_manager.set_enabled(APP_ID, True)
        self.assertTrue(self.app_manager.enabled(APP_ID))
        self.app_manager.set_enabled(APP_ID, False)
        self.assertFalse(self.app_manager.enabled(APP_ID))


class TestLoadAppFromJSONFile(TempDirFixture):

    def test_ok(self):
        json_file = self.new_path / 'test_app.json'
        json_file.write_text(APP_DEF.to_json(), encoding='utf-8')
        app_def = load_app_from_json_file(json_file)
        self.assertEqual(app_def.id, APP_ID)
        self.assertEqual(app_def, APP_DEF)

    def test_file_missing(self):
        json_file = self.new_path / 'test_app.json'
        with self.assertRaises(ValueError):
            load_app_from_json_file(json_file)

    def test_invalid_json(self):
        json_file = self.new_path / 'test_app.json'
        json_file.write_text('(╯°□°）╯︵ ┻━┻', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_app_from_json_file(json_file)

    def test_formatting_invariant(self):
        app_json_1 = '''{
            "name":               "app",
            "requestor_env":      "env",
            "requestor_prereq":   {
                "x": "y"
            },
            "max_benchmark_score": 0.0
        }'''
        json_file1 = self.new_path / 'app1.json'
        json_file1.write_text(app_json_1, encoding='utf-8')

        app_json_2 = '''{
            "name": "app",
            "max_benchmark_score": 0.0,
            "requestor_env": "env",
            "requestor_prereq": {"x": "y"}
        }'''
        json_file2 = self.new_path / 'app2.json'
        json_file2.write_text(app_json_2)

        app1 = load_app_from_json_file(json_file1)
        app2 = load_app_from_json_file(json_file2)
        self.assertEqual(app1, app2)
        self.assertEqual(app1.id, app2.id)


class TestLoadAppsFromDir(TempDirFixture):

    def test_register(self):
        app_file = self.new_path / 'test_app.json'
        bogus_file = self.new_path / 'bogus.json'
        app_file.write_text(APP_DEF.to_json(), encoding='utf-8')
        bogus_file.write_text('(╯°□°）╯︵ ┻━┻', encoding='utf-8')
        loaded_apps = list(load_apps_from_dir(self.new_path))
        self.assertEqual(loaded_apps, [(app_file, APP_DEF)])
