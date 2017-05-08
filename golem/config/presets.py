import logging

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

    def update_hw_preset(self, name, preset_dict):
        preset = HardwarePreset.get(name=name)
        preset.apply(preset_dict)
        preset.update()

    def remove_hw_preset(self, name):
        HardwarePreset.delete().where(name=name)

    def activate_hw_preset(self, name):
        raise NotImplementedError
