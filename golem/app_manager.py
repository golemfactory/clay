import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Iterator

from dataclasses import dataclass, field
from dataclasses_json import config, dataclass_json
from marshmallow import fields as mm_fields

from golem.task.envmanager import EnvironmentManager

logger = logging.getLogger(__name__)


@dataclass_json
@dataclass
class AppDefinition:
    name: str
    requestor_env: str
    requestor_prereq: Dict[str, Any] = field(metadata=config(
        encoder=json.dumps,
        decoder=json.loads,
        mm_field=mm_fields.Dict(keys=mm_fields.Str())
    ))
    max_benchmark_score: float
    version: str = '0.0'
    description: str = ''
    author: str = ''
    license: str = ''


def load_app_from_json_file(json_file: Path) -> AppDefinition:
    """ Parse application definition from the given JSON file. Raise ValueError
        if the given file doesn't contain a valid definition. """
    try:
        app_json = json_file.read_text(encoding='utf-8')
        # pylint: disable=no-member
        return AppDefinition.from_json(app_json)  # type: ignore
        # pylint: enable=no-member
    except (OSError, ValueError, KeyError):
        msg = f"Error parsing app definition from file '{json_file}'."
        logger.exception(msg)
        raise ValueError(msg)


def load_apps_from_dir(app_dir: Path) -> Iterator[AppDefinition]:
    """ Read every file in the given directory and attempt to parse it. Ignore
        files which don't contain valid app definitions. """
    for json_file in app_dir.iterdir():
        try:
            yield load_app_from_json_file(json_file)
        except ValueError:
            continue


class AppManager:
    """ Manager class for applications using Task API. """

    def __init__(self, env_manager: EnvironmentManager) -> None:
        self._env_manager = env_manager
        self._apps: Dict[str, AppDefinition] = {}
        self._state: Dict[str, bool] = {}

    def register_app(self, app: AppDefinition) -> None:
        """ Register an application in the manager. """
        if app.name in self._apps:
            raise ValueError(f"Application '{app.name}' already registered.")
        self._apps[app.name] = app
        self._state[app.name] = False
        logger.info("Application '%s' registered.", app.name)

    def enabled(self, app_name: str) -> bool:
        """ Check if an application with the given name is registered in the
            manager and enabled. """
        return app_name in self._state and self._state[app_name]

    def set_enabled(self, app_name: str, enabled: bool) -> None:
        """ Enable or disable an application. Raise an error if the application
            is not registered or the environment associated with the application
            is not available. """
        if app_name not in self._apps:
            raise ValueError(f"Application '{app_name}' not registered.")
        env_id = self._apps[app_name].requestor_env
        if not self._env_manager.enabled(env_id):
            raise ValueError(f"Environment '{env_id}' not available.")
        self._state[app_name] = enabled
        logger.info(
            "Application '%s' %s.",
            app_name,
            'enabled' if enabled else 'disabled')

    def apps(self) -> List[AppDefinition]:
        """ Get all registered apps. """
        return list(self._apps.values())

    def app(self, app_name: str) -> AppDefinition:
        """ Get an app with given name (assuming it is registered). """
        return self._apps[app_name]
