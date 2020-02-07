import logging
from pathlib import Path
from typing import Iterator, Type, Tuple

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from marshmallow import fields as mm_fields
from golem_task_api.apputils.app_definition import AppDefinitionBase

from golem.marketplace import (
    RequestorMarketStrategy,
    requestor_market_strategy_encode,
    requestor_market_strategy_decode,
    DEFAULT_REQUESTOR_MARKET_STRATEGY,
)

logger = logging.getLogger(__name__)

AppId = str


@dataclass_json
@dataclass
class AppDefinition(AppDefinitionBase):

    market_strategy: Type[RequestorMarketStrategy] = field(
        metadata=config(
            encoder=requestor_market_strategy_encode,
            decoder=requestor_market_strategy_decode,
            mm_field=mm_fields.Str(),
        ),
        default=DEFAULT_REQUESTOR_MARKET_STRATEGY,
    )

    @classmethod
    def from_json(cls, json_str: str) -> 'AppDefinition':
        raise NotImplementedError  # A stub to silence the linters

    def to_json(self) -> str:
        raise NotImplementedError  # A stub to silence the linters


def load_app_from_json_file(json_file: Path) -> AppDefinition:
    """ Parse application definition from the given JSON file. Raise ValueError
        if the given file doesn't contain a valid definition. """
    try:
        app_json = json_file.read_text(encoding='utf-8')
        return AppDefinition.from_json(app_json)
    except (OSError, ValueError, KeyError):
        msg = f"Error parsing app definition from file '{json_file}'."
        logger.exception(msg)
        raise ValueError(msg)


def load_apps_from_dir(app_dir: Path) -> Iterator[Tuple[Path, AppDefinition]]:
    """ Read every file in the given directory and attempt to parse it. Ignore
        files which don't contain valid app definitions. """
    for json_file in app_dir.iterdir():
        try:
            yield (json_file, load_app_from_json_file(json_file))
        except ValueError:
            continue


def app_json_file_name(app_def: AppDefinition) -> str:
    filename = f"{app_def.name}_{app_def.version}_{app_def.id}.json"
    filename = sanitize_filename(filename, replacement_text="_")
    return filename
