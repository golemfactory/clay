import logging
from multiprocessing import cpu_count
from typing import Union, List, Tuple, Optional, Dict
import humanize
import psutil
from psutil import virtual_memory

from golem.appconfig import \
    MIN_MEMORY_SIZE, \
    MIN_DISK_SPACE, \
    MIN_CPU_CORES, \
    DEFAULT_HARDWARE_PRESET_NAME as DEFAULT, \
    CUSTOM_HARDWARE_PRESET_NAME as CUSTOM
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.common import is_osx, is_windows, is_linux
from golem.core.fileshelper import free_partition_space
from golem.model import HardwarePreset

logger = logging.getLogger(__name__)


MAX_CPU_WINDOWS = 32
MAX_CPU_MACOS = 16


def cpu_cores_available() -> List[int]:
    """
    Lists CPU cores affined to the process (Linux, Windows) or the available
    core count (macOS). On Linux, tries to remove the first core from the list
    if no custom affinity has been set.
    :return list: A list of CPU cores available for computation.
    """
    core_count = cpu_count()

    try:
        affinity = psutil.Process().cpu_affinity()
    except Exception as e:
        logger.debug("Couldn't read CPU affinity: %r", e)
        affinity = list(range(0, core_count - 1))

    # FIXME: The Linux case will no longer be valid when VM computations are
    #        introduced.
    if is_linux():
        if len(affinity) == core_count and 0 in affinity:
            affinity.remove(0)
    else:
        reserved_cpu = 1
        if is_osx() and len(affinity) > MAX_CPU_MACOS:
            affinity = affinity[:MAX_CPU_MACOS]
            reserved_cpu = 0
        elif is_windows() and len(affinity) > MAX_CPU_WINDOWS:
            affinity = affinity[:MAX_CPU_WINDOWS]
            reserved_cpu = 0
        affinity = list(range(0, len(affinity) - reserved_cpu))
    cpu_list = affinity or [0]
    logger.debug('cpus() -> %r', cpu_list)
    return cpu_list



def memory_available() -> int:
    """
    :return int: 3/4 of total available memory in KiB
    """
    return max(int(virtual_memory().total * 0.75 / 1024), MIN_MEMORY_SIZE)


class HardwarePresets(object):

    default_values = {
        'cpu_cores': len(cpu_cores_available()),
        'memory': memory_available(),
        'disk': MIN_DISK_SPACE
    }

    CUSTOM_VALUES = dict(default_values)

    working_dir: Optional[str] = None

    @classmethod
    def initialize(cls, working_dir: str):
        cls.working_dir = working_dir
        cls.default_values['disk'] = free_partition_space(cls.working_dir)

        HardwarePreset.get_or_create(name=DEFAULT,
                                     defaults=cls.default_values)
        HardwarePreset.get_or_create(name=CUSTOM,
                                     defaults=cls.CUSTOM_VALUES)

    @classmethod
    def update_config(cls,
                      preset_or_name: Union[str, HardwarePreset],
                      config: ClientConfigDescriptor) -> bool:
        """
        Changes given config with values from given preset
        :param preset_or_name: preset object or its name
        :param config: subject to change
        :return: True if config was not initial and has changed, False otherwise
        """
        old_config = dict(config.__dict__)
        is_initial_config = \
            config.num_cores == 0 \
            and config.max_resource_size == 0 \
            and config.max_memory_size == 0

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

        if not is_initial_config and config.__dict__ != old_config:
            logger.info("Config change detected.")
            return True

        return False

    @classmethod
    def from_config(cls, config: ClientConfigDescriptor) -> HardwarePreset:
        return HardwarePreset(
            name=config.hardware_preset_name,
            cpu_cores=config.num_cores,
            memory=config.max_memory_size,
            disk=config.max_resource_size
        )

    @classmethod
    def caps(cls) -> Dict[str, int]:
        cls._assert_initialized()
        return {
            'cpu_cores': len(cpu_cores_available()),
            'memory': memory_available(),
            'disk': free_partition_space(cls.working_dir)
        }

    @classmethod
    def values(cls, preset_or_name: Union[str, HardwarePreset]) \
            -> Tuple[str, Dict[str, int]]:
        preset_or_name = preset_or_name or DEFAULT

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
    def cpu_cores(cls, core_num: int) -> int:
        available = len(cpu_cores_available())
        return max(min(core_num, available), MIN_CPU_CORES)

    @classmethod
    def memory(cls, mem_size: int) -> int:
        available = memory_available()
        return max(min(mem_size, available), MIN_MEMORY_SIZE)

    @classmethod
    def disk(cls, disk_space: int) -> int:
        cls._assert_initialized()
        available = free_partition_space(cls.working_dir)
        return max(min(disk_space, available), MIN_DISK_SPACE)

    @classmethod
    def _assert_initialized(cls):
        if not cls.working_dir:
            raise EnvironmentError("Class not initialized")
