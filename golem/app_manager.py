import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Iterator, Tuple

from dataclasses import dataclass, field
from dataclasses_json import config, dataclass_json
from marshmallow import fields as mm_fields

logger = logging.getLogger(__name__)

AppId = str


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

    @classmethod
    def from_json(cls, json_str: str) -> 'AppDefinition':
        raise NotImplementedError  # A stub to silence the linters

    def to_json(self) -> str:
        raise NotImplementedError  # A stub to silence the linters


def load_app_from_json_file(json_file: Path) -> Tuple[AppId, AppDefinition]:
    """ Parse application definition from the given JSON file. Raise ValueError
        if the given file doesn't contain a valid definition. """
    try:
        app_json = json_file.read_text(encoding='utf-8')
        app_id = hashlib.md5(app_json.encode('utf-8')).hexdigest()
        return app_id, AppDefinition.from_json(app_json)
    except (OSError, ValueError, KeyError):
        msg = f"Error parsing app definition from file '{json_file}'."
        logger.exception(msg)
        raise ValueError(msg)


def load_apps_from_dir(app_dir: Path) -> Iterator[Tuple[AppId, AppDefinition]]:
    """ Read every file in the given directory and attempt to parse it. Ignore
        files which don't contain valid app definitions. """
    for json_file in app_dir.iterdir():
        try:
            yield load_app_from_json_file(json_file)
        except ValueError:
            continue


class AppManager:
    """ Manager class for applications using Task API. """

    def __init__(self) -> None:
        self._apps: Dict[AppId, AppDefinition] = {}
        self._state: Dict[AppId, bool] = {}

    def register_app(self, app_id: AppId, app: AppDefinition) -> None:
        """ Register an application in the manager. """
        if app_id in self._apps:
            raise ValueError(
                f"Application already registered. "
                f"app_name={app.name} app_id={app_id}")
        self._apps[app_id] = app
        self._state[app_id] = False
        logger.info(
            "Application registered. app_name=%r app_id=%r", app.name, app_id)

    def enabled(self, app_id: AppId) -> bool:
        """ Check if an application with the given ID is registered in the
            manager and enabled. """
        return app_id in self._state and self._state[app_id]

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
