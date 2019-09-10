from unittest import TestCase

from golem.app_manager import (
    AppDefinition,
    AppManager,
    load_app_from_json_file,
    load_apps_from_dir
)
from golem.testutils import TempDirFixture

APP_NAME = 'test_app'
APP_DEF = AppDefinition(
    name=APP_NAME,
    requestor_env='test_env',
    requestor_prereq={
        'key1': 'value',
        'key2': [1, 2, 3]
    },
    max_benchmark_score=1.0
)


class AppManagerTestBase(TestCase):

    def setUp(self):
        super().setUp()
        self.app_manager = AppManager()


class TestRegisterApp(AppManagerTestBase):

    def test_register_app(self):
        self.app_manager.register_app(APP_DEF)
        self.assertEqual(self.app_manager.apps(), [APP_DEF])
        self.assertEqual(self.app_manager.app(APP_NAME), APP_DEF)
        self.assertFalse(self.app_manager.enabled(APP_NAME))

    def test_re_register(self):
        self.app_manager.register_app(APP_DEF)
        with self.assertRaises(ValueError):
            self.app_manager.register_app(APP_DEF)


class TestSetEnabled(AppManagerTestBase):

    def test_app_not_registered(self):
        with self.assertRaises(ValueError):
            self.app_manager.set_enabled(APP_NAME, True)

    def test_enable_disable(self):
        self.app_manager.register_app(APP_DEF)
        self.assertFalse(self.app_manager.enabled(APP_NAME))
        self.app_manager.set_enabled(APP_NAME, True)
        self.assertTrue(self.app_manager.enabled(APP_NAME))
        self.app_manager.set_enabled(APP_NAME, False)
        self.assertFalse(self.app_manager.enabled(APP_NAME))


class TestLoadAppFromJSONFile(TempDirFixture):

    def test_ok(self):
        json_file = self.new_path / 'test_app.json'
        json_file.write_text(APP_DEF.to_json(), encoding='utf-8')  # noqa pylint: disable=no-member
        loaded_app = load_app_from_json_file(json_file)
        self.assertEqual(loaded_app, APP_DEF)

    def test_file_missing(self):
        json_file = self.new_path / 'test_app.json'
        with self.assertRaises(ValueError):
            load_app_from_json_file(json_file)

    def test_invalid_json(self):
        json_file = self.new_path / 'test_app.json'
        json_file.write_text('(╯°□°）╯︵ ┻━┻', encoding='utf-8')
        with self.assertRaises(ValueError):
            load_app_from_json_file(json_file)


class TestLoadAppsFromDir(TempDirFixture):

    def test_register(self):
        app_file = self.new_path / 'test_app.json'
        bogus_file = self.new_path / 'bogus.json'
        app_file.write_text(APP_DEF.to_json(), encoding='utf-8')  # noqa pylint: disable=no-member
        bogus_file.write_text('(╯°□°）╯︵ ┻━┻', encoding='utf-8')
        loaded_apps = list(load_apps_from_dir(self.new_path))
        self.assertEqual(loaded_apps, [APP_DEF])
