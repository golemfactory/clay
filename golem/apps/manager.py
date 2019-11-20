import logging
from typing import Dict, List, Tuple

from golem.apps import AppId, AppDefinition
from golem.model import AppConfiguration

logger = logging.getLogger(__name__)


class AppManager:
    """ Manager class for applications using Task API. """

    def __init__(self) -> None:
        self._apps: Dict[AppId, AppDefinition] = {}
        self._state = AppStates()

    def register_app(self, app: AppDefinition) -> None:
        """ Register an application in the manager. """
        app_id = app.id
        if app_id in self._apps:
            raise ValueError(
                f"Application already registered. "
                f"app_name={app.name} app_id={app_id}")
        self._apps[app_id] = app
        if app_id not in self._state:
            self._state[app_id] = False
        logger.info(
            "Application registered. app_name=%r app_id=%r", app.name, app_id)

    def enabled(self, app_id: AppId) -> bool:
        """ Check if an application with the given ID is registered in the
            manager and enabled. """
        return app_id in self._apps and \
            app_id in self._state and \
            self._state[app_id]

    def set_enabled(self, app_id: AppId, enabled: bool) -> None:
        """ Enable or disable an application. Raise an error if the application
            is not registered or the environment associated with the application
            is not available. """
        if app_id not in self._apps:
            raise ValueError(f"Application not registered. app_id={app_id}")
        self._state[app_id] = enabled
        logger.info(
            "Application %s. app_id=%r",
            'enabled' if enabled else 'disabled', app_id)

    def apps(self) -> List[Tuple[AppId, AppDefinition]]:
        """ Get all registered apps. """
        return list(self._apps.items())

    def app(self, app_id: AppId) -> AppDefinition:
        """ Get an app with given ID (assuming it is registered). """
        return self._apps[app_id]


class AppStates:

    def __contains__(self, item):
        if not isinstance(item, str):
            self._raise_no_str_type(item)

        return AppConfiguration.select(AppConfiguration.app_id) \
            .where(AppConfiguration.app_id == item) \
            .exists()

    def __getitem__(self, item):
        if not isinstance(item, str):
            self._raise_no_str_type(item)
        try:
            return AppConfiguration \
                .get(AppConfiguration.app_id == item) \
                .enabled
        except AppConfiguration.DoesNotExist:
            raise KeyError(item)

    def __setitem__(self, key, val):
        if not isinstance(key, str):
            self._raise_no_str_type(key)
        if not isinstance(val, bool):
            raise TypeError(f"Value is of type {type(val)}; bool expected")

        AppConfiguration.insert(app_id=key, enabled=val).upsert().execute()

    @staticmethod
    def _raise_no_str_type(item):
        raise TypeError(f"Key is of type {type(item)}; str expected")
