import json
from pathlib import Path
from typing import Dict

from golem.core.common import update_dict


class JsonFileConfig:

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> Dict:
        """ Reads configuration from the file. Returns an empty dict if the file
            does not exist """
        if not self._path.exists():
            return dict()

        with open(str(self._path)) as config_file:
            return json.load(config_file)

    def write(self, config: Dict) -> None:
        """ Writes configuration to thea file. Creates the parent directories
            and the file itself if needed """
        self._path.parent.mkdir(exist_ok=True)

        with open(str(self._path), 'w') as config_file:
            json.dump(config, config_file)

    def update(self, update: Dict) -> None:
        """ Persists a deep update of the configuration dictionary """
        config = self.read()
        update_dict(config, update)
        self.write(config)
