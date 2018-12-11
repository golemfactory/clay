import logging
from typing import Dict, Optional, Tuple, Union

import humanize

from golem import appconfig, hardware
from golem.appconfig import CUSTOM_HARDWARE_PRESET_NAME as CUSTOM, \
    DEFAULT_HARDWARE_PRESET_NAME as DEFAULT
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.model import HardwarePreset
from golem.rpc import utils as rpc_utils

logger = logging.getLogger(__name__)


class HardwarePresets:

    default_values: Optional[Dict[str, int]] = None
    custom_values: Optional[Dict[str, int]] = None

    @classmethod
    def initialize(cls, working_dir: str):
        hardware.initialize(working_dir)

        cls.default_values = hardware.caps()
        cls.custom_values = dict(cls.default_values)

        HardwarePreset.get_or_create(name=DEFAULT,
                                     defaults=cls.default_values)
        HardwarePreset.get_or_create(name=CUSTOM,
                                     defaults=cls.custom_values)

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
            cpu_cores=hardware.cap_cpus(config.num_cores),
            memory=hardware.cap_memory(config.max_memory_size),
            disk=hardware.cap_disk(config.max_resource_size),
        )

    @classmethod
    def caps(cls) -> Dict[str, int]:
        return hardware.caps()

    @classmethod
    def values(cls, preset_or_name: Union[str, HardwarePreset]) \
            -> Tuple[str, Dict[str, int]]:
        preset_or_name = preset_or_name or DEFAULT

        if isinstance(preset_or_name, str):
            preset = HardwarePreset.get(name=preset_or_name)
        else:
            preset = preset_or_name

        return preset.name, {
            'cpu_cores': hardware.cap_cpus(preset.cpu_cores),
            'memory': hardware.cap_memory(preset.memory),
            'disk': hardware.cap_disk(preset.disk)
        }


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

    @staticmethod
    def __preset_to_dict(preset):
        return preset if isinstance(preset, dict) else preset.to_dict()

    @staticmethod
    def __sanitize_preset_name(name):
        if not name or name == appconfig.DEFAULT_HARDWARE_PRESET_NAME:
            return appconfig.CUSTOM_HARDWARE_PRESET_NAME
        return name
