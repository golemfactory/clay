from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field, asdict

from golem.app_manager import AppManager
from golem.core.common import get_timestamp_utc
from golem.report import EventPublisher
from golem.rpc import utils as rpc_utils
from golem.rpc.mapping.rpceventnames import Apps


MAX_DISCOVERED_APPS: int = 50


@dataclass
class DiscoveredApp:
    name: str
    definition: Optional[Dict[str, Any]] = None
    discovery_ts: float = field(default_factory=get_timestamp_utc)


class AppManagerRPC:

    def __init__(self, app_manager: AppManager) -> None:
        self._app_manager: AppManager = app_manager
        self._discovered_apps: List[DiscoveredApp] = list()

    def _app_discovered(
        self,
        app_name: str,
        definition: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._app_manager.registered(app_name):
            return

        discovered_app = DiscoveredApp(app_name, definition=definition)
        self._discovered_apps.append(discovered_app)
        self._refresh_discovered_apps()

        EventPublisher.publish(
            Apps.evt_app_discovered,
            app_name,
            definition)

    def _refresh_discovered_apps(self) -> None:
        """ Update the internal discovered apps collection based on their status
            in the AppManager and the number of MAX_DISCOVERED_APPS stored """
        self._discovered_apps = [
            discovered_app for discovered_app in self._discovered_apps
            if not self._app_manager.registered(discovered_app.name)
        ]
        self._discovered_apps = self._discovered_apps[-MAX_DISCOVERED_APPS:]

    @rpc_utils.expose('apps')
    def _app_manager_apps_definitions(self) -> Dict[str, Any]:
        return {
            app.name: app.to_dict()
            for app in self._app_manager.apps()
        }

    @rpc_utils.expose('apps.status')
    def _app_manager_apps_statuses(self) -> Dict[str, bool]:
        return {
            app.name: self._app_manager.enabled(app.name)
            for app in self._app_manager.apps()
        }

    @rpc_utils.expose('apps.discovered')
    def _app_manager_apps_discovered(self) -> Dict[str, bool]:
        self._refresh_discovered_apps()
        return {
            discovered_app.name: asdict(discovered_app)
            for discovered_app in self._discovered_apps
        }

    @rpc_utils.expose('app.enabled.set')
    def _app_manager_app_set_enabled(
            self,
            app_name: str,
            enabled: bool,
    ) -> None:
        self._app_manager.set_enabled(app_name, enabled)
