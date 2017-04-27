import multiprocessing

import math
import psutil
from psutil import virtual_memory

from golem.appconfig import logger, MIN_MEMORY_SIZE, MIN_DISK_SPACE, MIN_CPU_CORES, DEFAULT_HARDWARE_PRESET_NAME
from golem.core.fileshelper import free_partition_space
from golem.model import HardwarePreset


def cpu_cores_available():
    """
    Retrieves available CPU cores except for the first one. Tries to read process' CPU affinity first.
    :return list: Available cpu cores except the first one.
    """
    try:
        affinity = psutil.Process().cpu_affinity()
        return affinity[1:] or affinity
    except Exception as e:
        logger.debug("Couldn't read CPU affinity: {}".format(e))
        num_cores = multiprocessing.cpu_count()
        return range(1, num_cores) or [0]


def memory_available():
    """
    :return int: 3/4 of total available memory
    """
    return max(int(virtual_memory().total * 0.75) / 1024, MIN_MEMORY_SIZE)


AVAILABLE_CPU_CORES = cpu_cores_available()
AVAILABLE_MEMORY = memory_available()


class HardwarePresets(object):

    DEFAULT_NAME = DEFAULT_HARDWARE_PRESET_NAME
    DEFAULT_VALUES = dict(
        cpu_cores=0.75,
        memory=0.75,
        disk=0.5
    )

    CUSTOM_NAME = "custom"
    CUSTOM_VALUES = dict(DEFAULT_VALUES)

    working_dir = None

    @classmethod
    def initialize(cls, working_dir):
        HardwarePreset.get_or_create(name=cls.DEFAULT_NAME,
                                     defaults=cls.DEFAULT_VALUES)
        HardwarePreset.get_or_create(name=cls.CUSTOM_NAME,
                                     defaults=cls.CUSTOM_VALUES)
        cls.working_dir = working_dir

    @classmethod
    def update_config(cls, preset_or_name, config):
        values = cls.values(preset_or_name)
        setattr(config, 'num_cores', values['cpu_cores'])
        setattr(config, 'max_memory_size', values['memory'])
        setattr(config, 'max_resource_size', values['disk'])

    @classmethod
    def values(cls, preset_or_name):
        preset_or_name = preset_or_name or DEFAULT_HARDWARE_PRESET_NAME

        if isinstance(preset_or_name, str):
            preset = HardwarePreset.get(name=preset_or_name)
        else:
            preset = preset_or_name

        return dict(
            cpu_cores=cls.cpu_cores(preset.cpu_cores),
            memory=cls.memory(preset.memory),
            disk=cls.disk(preset.disk)
        )

    @classmethod
    def cpu_cores(cls, fraction):
        fraction = cls.fraction(fraction)
        cores_len = len(AVAILABLE_CPU_CORES)
        requested = round(fraction * cores_len)
        return max(requested, MIN_CPU_CORES)

    @classmethod
    def memory(cls, fraction):
        fraction = cls.fraction(fraction)
        requested = round(fraction * AVAILABLE_MEMORY)
        return max(requested, MIN_MEMORY_SIZE)

    @classmethod
    def disk(cls, fraction):
        if not cls.working_dir:
            raise EnvironmentError("Class not properly initialized")

        fraction = cls.fraction(fraction)
        available = free_partition_space(cls.working_dir)
        requested = math.floor(fraction * available / 1024)

        return int(max(requested, MIN_DISK_SPACE))

    @classmethod
    def fraction(cls, fraction):
        if not fraction:
            return 0.
        return max(0., min(1., fraction))
