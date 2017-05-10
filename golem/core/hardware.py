import multiprocessing

import psutil
from psutil import virtual_memory

from golem.appconfig import logger,\
    MIN_MEMORY_SIZE,\
    MIN_DISK_SPACE,\
    MIN_CPU_CORES,\
    DEFAULT_HARDWARE_PRESET_NAME,\
    CUSTOM_HARDWARE_PRESET_NAME
from golem.core.fileshelper import free_partition_space
from golem.model import HardwarePreset


def cpu_cores_available():
    """Retrieves available CPU cores except for the first one. Tries to read
       process' CPU affinity first.
    :return list: Available cpu cores except the first one.
    """
    try:
        affinity = psutil.Process().cpu_affinity()
        return affinity[:-1] or affinity
    except Exception as e:
        logger.debug("Couldn't read CPU affinity: {}".format(e))
        num_cores = multiprocessing.cpu_count()
        return range(0, num_cores - 1) or [0]


def memory_available():
    """
    :return int: 3/4 of total available memory
    """
    return max(int(virtual_memory().total * 0.75) / 1024, MIN_MEMORY_SIZE)


class HardwarePresets(object):

    DEFAULT_NAME = DEFAULT_HARDWARE_PRESET_NAME
    default_values = {
        u'cpu_cores': len(cpu_cores_available()),
        u'memory': memory_available(),
        u'disk': MIN_DISK_SPACE
    }

    CUSTOM_NAME = CUSTOM_HARDWARE_PRESET_NAME
    CUSTOM_VALUES = dict(default_values)

    working_dir = None

    @classmethod
    def initialize(cls, working_dir):
        cls.working_dir = working_dir
        cls.default_values[u'disk'] = free_partition_space(cls.working_dir)

        HardwarePreset.get_or_create(name=cls.DEFAULT_NAME,
                                     defaults=cls.default_values)
        HardwarePreset.get_or_create(name=cls.CUSTOM_NAME,
                                     defaults=cls.CUSTOM_VALUES)

    @classmethod
    def update_config(cls, preset_or_name, config):
        name, values = cls.values(preset_or_name)
        setattr(config, 'hardware_preset_name', name)
        setattr(config, 'num_cores', values[u'cpu_cores'])
        setattr(config, 'max_memory_size', values[u'memory'])
        setattr(config, 'max_resource_size', values[u'disk'])

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
            u'cpu_cores': len(cpu_cores_available()),
            u'memory': memory_available(),
            u'disk': free_partition_space(cls.working_dir)
        }

    @classmethod
    def values(cls, preset_or_name):
        preset_or_name = preset_or_name or DEFAULT_HARDWARE_PRESET_NAME

        if isinstance(preset_or_name, basestring):
            preset = HardwarePreset.get(name=preset_or_name)
        else:
            preset = preset_or_name

        return preset.name, {
            u'cpu_cores': cls.cpu_cores(preset.cpu_cores),
            u'memory': cls.memory(preset.memory),
            u'disk': cls.disk(preset.disk)
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
            raise EnvironmentError(u"Class not initialized")
