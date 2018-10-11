import logging

from golem import appconfig
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset
from golem.rpc import utils as rpc_utils

log = logging.getLogger("golem.config")


class HardwarePresetsMixin(object):

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
