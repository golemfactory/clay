import logging
from typing import Optional, Union, Dict, Tuple

import humanize

from golem import appconfig
from golem.appconfig import MIN_DISK_SPACE, \
    DEFAULT_HARDWARE_PRESET_NAME as DEFAULT, \
    CUSTOM_HARDWARE_PRESET_NAME as CUSTOM, MIN_CPU_CORES, MIN_MEMORY_SIZE
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.fileshelper import free_partition_space
from golem.hardware import cpu_cores_available, memory_available
from golem.model import HardwarePreset
from golem.rpc import utils as rpc_utils

logger = logging.getLogger(__name__)


class HardwarePresets:

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


class HardwarePresetsMixin:

    @rpc_utils.expose('env.hw.caps')
    @staticmethod
    def get_hw_caps():
        return HardwarePresets.caps()

    @rpc_utils.expose('env.hw.presets')
    @staticmethod
    def get_hw_presets():
        presets = HardwarePreset.select()
        return [p.to_dict() for p in presets]

    @rpc_utils.expose('env.hw.preset')
    @staticmethod
    def get_hw_preset(name):
        return HardwarePreset.get(name=name).to_dict()

    @rpc_utils.expose('env.hw.preset.create')
    @staticmethod
    def create_hw_preset(preset_dict):
        preset = HardwarePreset(**preset_dict)
        preset.save()
        return preset.to_dict()

    @rpc_utils.expose('env.hw.preset.update')
    @classmethod
    def update_hw_preset(cls, preset):
        preset_dict = cls.__preset_to_dict(preset)
        name = cls.__sanitize_preset_name(preset_dict['name'])

        preset = HardwarePreset.get(name=name)
        preset.apply(preset_dict)
        preset.save()
        return preset.to_dict()

    @classmethod
    def upsert_hw_preset(cls, preset):
        preset_dict = cls.__preset_to_dict(preset)
        name = cls.__sanitize_preset_name(preset_dict['name'])

        defaults = dict(preset_dict)
        defaults.pop('name')

        preset, created = HardwarePreset.get_or_create(name=name,
                                                       defaults=defaults)
        if not created:
            preset.apply(preset_dict)
            preset.save()

        return preset.to_dict()

    @rpc_utils.expose('env.hw.preset.delete')
    @staticmethod
    def delete_hw_preset(name):
        if name in [
                appconfig.CUSTOM_HARDWARE_PRESET_NAME,
                appconfig.DEFAULT_HARDWARE_PRESET_NAME,
        ]:
            raise ValueError('Cannot remove preset with name: ' + name)

        deleted = HardwarePreset \
            .delete() \
            .where(HardwarePreset.name == name) \
            .execute()

        return bool(deleted)

    def activate_hw_preset(self, name, run_benchmarks=False):
        raise NotImplementedError

    @staticmethod
    def __preset_to_dict(preset):
        return preset if isinstance(preset, dict) else preset.to_dict()

    @staticmethod
    def __sanitize_preset_name(name):
        if not name or name == appconfig.DEFAULT_HARDWARE_PRESET_NAME:
            return appconfig.CUSTOM_HARDWARE_PRESET_NAME
        return name
