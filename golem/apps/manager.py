import logging
from typing import Dict, List, Tuple
from pathlib import Path

from dataclasses import asdict

from golem.apps import AppId, AppDefinition, load_apps_from_dir
from golem.apps.downloader import download_definitions
from golem.model import AppConfiguration
from golem.report import EventPublisher
from golem.rpc.mapping.rpceventnames import App

logger = logging.getLogger(__name__)


class AppManager:
    """ Manager class for applications using Task API. """

    def __init__(self, app_dir: Path) -> None:
        self._apps: Dict[AppId, AppDefinition] = {}
        self._state = AppStates()
        self._app_file_names: Dict[AppId, Path] = dict()

        # Download default apps then load from path
        new_apps = download_definitions(app_dir)
        for app_def_path, app_def in load_apps_from_dir(app_dir):
            self.register_app(app_def)
            self._app_file_names[app_def.id] = app_def_path

        # Notify about newly available apps
        for app in new_apps:
            EventPublisher.publish(App.evt_new_definiton, asdict(app))

    def registered(self, app_id) -> bool:
        return app_id in self._apps

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
            "Application registered. app_name=%r:%r, state=%r, app_id=%r",
            app.name,
            app.version,
            self._state[app_id],
            app_id,
        )

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

    def delete(self, app_id: AppId) -> bool:
        # Delete self._state from the database first
        del self._state[app_id]
        del self._apps[app_id]
        self._app_file_names[app_id].unlink()
        return True


class AppStates:

    def __contains__(self, key):
        if not isinstance(key, str):
            self._raise_no_str_type(key)

        return AppConfiguration.select(AppConfiguration.app_id) \
            .where(AppConfiguration.app_id == key) \
            .exists()

    def __getitem__(self, key):
        if not isinstance(key, str):
            self._raise_no_str_type(key)
        try:
            return AppConfiguration \
                .get(AppConfiguration.app_id == key) \
                .enabled
        except AppConfiguration.DoesNotExist:
            raise KeyError(key)

    def __setitem__(self, key, val):
        if not isinstance(key, str):
            self._raise_no_str_type(key)
        if not isinstance(val, bool):
            raise TypeError(f"Value is of type {type(val)}; bool expected")

        AppConfiguration.insert(app_id=key, enabled=val).upsert().execute()

    def __delitem__(self, key):
        try:
            AppConfiguration.delete() \
                .where(AppConfiguration.app_id == key).execute()
        except AppConfiguration.DoesNotExist:
            logger.warning('Can not delete app, not found. id=%e', key)
            raise KeyError(key)

    @staticmethod
    def _raise_no_str_type(key):
        raise TypeError(f"Key is of type {type(key)}; str expected")
