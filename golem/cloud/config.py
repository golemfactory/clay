from pathlib import Path
import logging
from typing import Optional
from tcutils.paths import get_path
from tcutils.config import Configuration

from golem.core import simpleenv
from .const import DEFAULT_CLOUD_CONFIG_DIR, DEFAULT_CLOUD_CONFIG_FILE

logger = logging.getLogger(__name__)


def get_cloud_config_dir(data_dir: Optional[str]=None) -> Path:
    if data_dir is None:
        data_dir = simpleenv.get_local_datadir("default")
    data_path = Path(data_dir) / DEFAULT_CLOUD_CONFIG_DIR
    if not data_path.exists():
        data_path.mkdir(parents=True, exist_ok=True)
    return data_path


def get_config_path(
    data_dir: Optional[str] = None,
    config_file: Optional[str] = DEFAULT_CLOUD_CONFIG_FILE,
) -> Path:
    config_dir_path = get_cloud_config_dir(data_dir)
    return config_dir_path / config_file


def load_config(config_path, config_class=Configuration):
    """Load configuration."""
    config_path = get_path(config_path)
    if not config_path:
        raise FileNotFoundError(
            f'`config_path` "{config_path}" does not exist.')
    if not issubclass(config_class, Configuration):
        raise TypeError('`config_class` is not inherited from Configuration')
    config = config_class.load(config_path=config_path)
    return config
