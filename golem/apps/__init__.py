import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Iterator, Type

from dataclasses import dataclass, field
from dataclasses_json import dataclass_json, config
from marshmallow import fields as mm_fields

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
class AppDefinition:
    name: str
    requestor_env: str
    requestor_prereq: Dict[str, Any] = field(metadata=config(
        mm_field=mm_fields.Dict(keys=mm_fields.Str())
    ))
    max_benchmark_score: float
    version: str = '0.0'
    description: str = ''
    author: str = ''
    license: str = ''

    market_strategy: Type[RequestorMarketStrategy] = field(
        metadata=config(
            encoder=requestor_market_strategy_encode,
            decoder=requestor_market_strategy_decode,
            mm_field=mm_fields.Str(),
        ),
        default=DEFAULT_REQUESTOR_MARKET_STRATEGY,
    )

    @property
    def id(self) -> AppId:
        return hashlib.blake2b(  # pylint: disable=no-member
            self.to_json().encode('utf-8'),
            digest_size=16
        ).hexdigest()

    @classmethod
    def from_json(cls, json_str: str) -> 'AppDefinition':
        raise NotImplementedError  # A stub to silence the linters

    def to_json(self) -> str:
        raise NotImplementedError  # A stub to silence the linters


def save_app_to_json_file(app_def: AppDefinition, json_file: Path) -> None:
    """ Save application definition to the given file in JSON format.
        Create parent directories if they don't exist. """
    try:
        json_file.parent.mkdir(parents=True, exist_ok=True)
        json_file.write_text(app_def.to_json())
    except OSError:
        msg = f"Error writing app definition to file '{json_file}."
        logger.exception(msg)
        raise ValueError(msg)


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


def load_apps_from_dir(app_dir: Path) -> Iterator[AppDefinition]:
    """ Read every file in the given directory and attempt to parse it. Ignore
        files which don't contain valid app definitions. """
    for json_file in app_dir.iterdir():
        try:
            yield load_app_from_json_file(json_file)
        except ValueError:
            continue
