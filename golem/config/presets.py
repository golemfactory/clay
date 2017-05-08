import logging

from golem.appconfig import CUSTOM_HARDWARE_PRESET_NAME, DEFAULT_HARDWARE_PRESET_NAME
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset

log = logging.getLogger("golem.config")


class HardwarePresetsMixin(object):

    @staticmethod
    def get_hw_caps():
        return HardwarePresets.caps()

    @staticmethod
    def get_hw_presets():
        presets = HardwarePreset.select()
        return [p.to_dict() for p in presets]

    @staticmethod
    def get_hw_preset(name):
        return HardwarePreset.get(name=name).to_dict()

    @staticmethod
    def create_hw_preset(preset_dict):
        preset = HardwarePreset(**preset_dict)
        preset.update()
        return preset

    @classmethod
    def update_hw_preset(cls, preset):
        preset_dict = cls.__preset_to_dict(preset)
        name = cls.__sanitize_preset_name(preset_dict['name'])

        preset = HardwarePreset.get(name=name)
        preset.apply(preset_dict)
        preset.update()
        return preset

    @classmethod
    def upsert_hw_preset(cls, preset):
        preset_dict = cls.__preset_to_dict(preset)
        name = cls.__sanitize_preset_name(preset_dict['name'])

        preset, _ = HardwarePreset.get_or_create(name=name)
        preset.apply(preset_dict)
        preset.update()
        return preset

    @staticmethod
    def remove_hw_preset(name):
        if name in [CUSTOM_HARDWARE_PRESET_NAME, DEFAULT_HARDWARE_PRESET_NAME]:
            raise ValueError('Cannot remove preset with name: ' + name)
        HardwarePreset.delete().where(name=name)

    def activate_hw_preset(self, name, run_benchmarks=False):
        raise NotImplementedError

    @staticmethod
    def __preset_to_dict(preset):
        return preset if isinstance(preset, dict) else preset.to_dict()

    @staticmethod
    def __sanitize_preset_name(name):
        if not name or name == DEFAULT_HARDWARE_PRESET_NAME:
            return CUSTOM_HARDWARE_PRESET_NAME
        return name
