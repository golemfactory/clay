from unittest import TestCase

from apps.appsmanager import AppsManager
from apps.blender.blenderenvironment import BlenderEnvironment
from apps.lux.luxenvironment import LuxRenderEnvironment


class TestAppsManager(TestCase):
    def test_get_env_list(self):
        app = AppsManager()
        app.load_apps()
        apps = app.get_env_list()
        assert any(isinstance(app, BlenderEnvironment) for app in apps)
        assert any(isinstance(app, LuxRenderEnvironment) for app in apps)
