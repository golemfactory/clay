import logging

from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset

log = logging.getLogger("golem.config")


class HardwarePresetsMixin(object):

    def get_hardware_caps(self):
        return HardwarePresets.caps()

    def get_presets(self):
        presets = HardwarePreset.select()
        return [p.to_dict() for p in presets]

    def create_preset(self, preset_dict):
        preset = HardwarePreset(**preset_dict)
        preset.update()

    def get_preset(self, name):
        return HardwarePreset.get(name=name).to_dict()

    def update_preset(self, name, preset_dict):
        preset = HardwarePreset.get(name=name)
        preset.apply(preset_dict)
        preset.update()

    def remove_preset(self, name):
        HardwarePreset.delete().where(name=name)

    def activate_preset(self, name):
        raise NotImplementedError
