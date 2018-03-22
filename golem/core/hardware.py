import logging

import humanize
import psutil
from psutil import virtual_memory

from golem.appconfig import \
    MIN_MEMORY_SIZE,\
    MIN_DISK_SPACE,\
    MIN_CPU_CORES,\
    DEFAULT_HARDWARE_PRESET_NAME,\
    CUSTOM_HARDWARE_PRESET_NAME
from golem.core.common import get_cpu_count, is_osx, is_windows,\
    MAX_CPU_MACOS, MAX_CPU_WINDOWS
from golem.core.fileshelper import free_partition_space
from golem.model import HardwarePreset

logger = logging.getLogger(__name__)


def cpu_cores_available():
    """Retrieves available CPU cores except for the first one. Tries to read
       process' CPU affinity first.
    :return list: Available cpu cores except the first one.
    """
    try:
        affinity = psutil.Process().cpu_affinity()
        if is_osx() and len(affinity) > MAX_CPU_MACOS:
            return list(range(0, MAX_CPU_MACOS))
        if is_windows() and len(affinity) > MAX_CPU_WINDOWS:
                return list(range(0, MAX_CPU_WINDOWS))
        return affinity[:-1] or affinity
    except Exception as e:
        logger.debug("Couldn't read CPU affinity: {}".format(e))
        num_cores = get_cpu_count()
        return list(range(0, num_cores - 1)) or [0]


def memory_available():
    """
    :return int: 3/4 of total available memory
    """
    return max(int(virtual_memory().total * 0.75) / 1024, MIN_MEMORY_SIZE)


class HardwarePresets(object):

    DEFAULT_NAME = DEFAULT_HARDWARE_PRESET_NAME
    default_values = {
        'cpu_cores': len(cpu_cores_available()),
        'memory': memory_available(),
        'disk': MIN_DISK_SPACE
    }

    CUSTOM_NAME = CUSTOM_HARDWARE_PRESET_NAME
    CUSTOM_VALUES = dict(default_values)

    working_dir = None

    @classmethod
    def initialize(cls, working_dir):
        cls.working_dir = working_dir
        cls.default_values['disk'] = free_partition_space(cls.working_dir)

        HardwarePreset.get_or_create(name=cls.DEFAULT_NAME,
                                     defaults=cls.default_values)
        HardwarePreset.get_or_create(name=cls.CUSTOM_NAME,
                                     defaults=cls.CUSTOM_VALUES)

    @classmethod
    def update_config(cls, preset_or_name, config):
        name, values = cls.values(preset_or_name)
        logger.info("updating config: name: %s, num_cores: %s, "
                    "max_memory_size: %s, max_resource_size: %s",
                    name, values['cpu_cores'],
                    humanize.naturalsize(values['memory'] * 1024, binary=True),
                    humanize.naturalsize(values['disk'] * 1024, binary=True))
        setattr(config, 'hardware_preset_name', name)
        setattr(config, 'num_cores', values['cpu_cores'])
        setattr(config, 'max_memory_size', values['memory'])
        setattr(config, 'max_resource_size', values['disk'])

    @classmethod
    def from_config(cls, config):
        return HardwarePreset(
            name=config.hardware_preset_name,
            cpu_cores=config.num_cores,
            memory=config.max_memory_size,
            disk=config.max_resource_size
        )

    @classmethod
    def caps(cls):
        cls._assert_initialized()
        return {
            'cpu_cores': len(cpu_cores_available()),
            'memory': memory_available(),
            'disk': free_partition_space(cls.working_dir)
        }

    @classmethod
    def values(cls, preset_or_name):
        preset_or_name = preset_or_name or DEFAULT_HARDWARE_PRESET_NAME

        if isinstance(preset_or_name, str):
            preset = HardwarePreset.get(name=preset_or_name)
        else:
            preset = preset_or_name

        return preset.name, {
            'cpu_cores': cls.cpu_cores(preset.cpu_cores),
            'memory': cls.memory(preset.memory),
            'disk': cls.disk(preset.disk)
        }

    @classmethod
    def cpu_cores(cls, core_num):
        available = len(cpu_cores_available())
        return max(min(core_num, available), MIN_CPU_CORES)

    @classmethod
    def memory(cls, mem_size):
        available = memory_available()
        return max(min(mem_size, available), MIN_MEMORY_SIZE)

    @classmethod
    def disk(cls, disk_space):
        cls._assert_initialized()
        available = free_partition_space(cls.working_dir)
        return max(min(disk_space, available), MIN_DISK_SPACE)

    @classmethod
    def _assert_initialized(cls):
        if not cls.working_dir:
            raise EnvironmentError("Class not initialized")
