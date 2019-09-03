import unittest
from unittest import mock

from freezegun import freeze_time

from golem.app_manager import AppManager
from golem.core.common import get_timestamp_utc
from golem.task.server.app_manager import AppManagerRPC, DiscoveredApp


MAX_APPS = 5


class TestDiscoveredApp(unittest.TestCase):

    @freeze_time("1000")
    def test_default_values(self):
        discovered_app = DiscoveredApp(name='test_app')
        self.assertEqual(discovered_app.name, 'test_app')
        self.assertIsNone(discovered_app.definition)
        self.assertEqual(discovered_app.discovery_ts, get_timestamp_utc())

    @freeze_time("1000")
    def test_custom_values(self):
        app_definition = dict(key='value')
        discovered_app = DiscoveredApp(
            name='test_app',
            definition=app_definition,
            discovery_ts=500)

        self.assertEqual(discovered_app.name, 'test_app')
        self.assertEqual(discovered_app.definition, app_definition)
        self.assertEqual(discovered_app.discovery_ts, 500)


@mock.patch('golem.task.server.app_manager.MAX_DISCOVERED_APPS', MAX_APPS)
@mock.patch('golem.task.server.app_manager.EventPublisher')
class TestAppDiscovered(unittest.TestCase):

    def setUp(self) -> None:
        self.app_manager = AppManager()
        self.app_manager_rpc = AppManagerRPC(self.app_manager)

    def test_app_limit(self, event_publisher):
        for i in range(MAX_APPS * 2):
            self.app_manager_rpc._app_discovered(str(i))

        assert event_publisher.publish.call_count == MAX_APPS * 2
        assert len(self.app_manager_rpc._discovered_apps) == MAX_APPS

        for i in range(MAX_APPS):
            discovered_app = self.app_manager_rpc._discovered_apps[i]
            assert discovered_app.name == str(MAX_APPS + i)

    def test_apps_registered(self, event_publisher):
        self.app_manager.registered = mock.Mock(return_value=True)

        for i in range(MAX_APPS):
            self.app_manager_rpc._app_discovered(str(i))

        assert event_publisher.publish.call_count == 0
        assert len(self.app_manager_rpc._discovered_apps) == 0

    def test_apps_registered_later_on(self, event_publisher):
        for i in range(MAX_APPS):
            self.app_manager_rpc._app_discovered(str(i))

        assert event_publisher.publish.call_count == MAX_APPS
        assert len(self.app_manager_rpc._discovered_apps) == MAX_APPS

        def registered(app_name: str) -> bool:
            return app_name != 'test_app'

        self.app_manager.registered = mock.Mock(side_effect=registered)
        self.app_manager_rpc._app_discovered('test_app')

        assert len(self.app_manager_rpc._discovered_apps) == 1


@mock.patch('golem.task.server.app_manager.MAX_DISCOVERED_APPS', MAX_APPS)
class TestAppManagerRPCMethods(unittest.TestCase):

    def setUp(self) -> None:
        self.app_manager = AppManager()
        self.app_manager_rpc = AppManagerRPC(self.app_manager)

        with mock.patch('golem.task.server.app_manager.EventPublisher'):
            for i in range(MAX_APPS):
                self.app_manager_rpc._app_discovered(str(i))

    def test_app_manager_apps_definitions(self):
        definitions = self.app_manager_rpc._app_manager_apps_definitions()
        assert isinstance(definitions, dict)
        assert all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in definitions.items())

    def test_app_manager_apps_statuses(self):
        statuses = self.app_manager_rpc._app_manager_apps_definitions()
        assert isinstance(statuses, dict)
        assert all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in statuses.items())

    def test_app_manager_apps_discovered(self):
        discovered_apps = self.app_manager_rpc._app_manager_apps_discovered()
        assert isinstance(discovered_apps, dict)
        assert all(
            isinstance(key, str) and isinstance(value, dict)
            for key, value in discovered_apps.items())

    def test_app_manager_app_set_enabled(self):
        self.app_manager.set_enabled = mock.Mock()
        self.app_manager_rpc._app_manager_app_set_enabled('test_app', True)
        self.app_manager.set_enabled.assert_called_with('test_app', True)
