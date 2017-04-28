import logging
from peewee import DoesNotExist

from golem.model import HardwarePreset

log = logging.getLogger("golem.config")


class HardwarePresetsMixin(object):

    def get_presets(self):
        try:
            presets = HardwarePreset.select()
            return [p.to_dict() for p in presets]
        except Exception as exc:
            log.debug("Cannot fetch hardware presets: {}"
                      .format(exc))
        return []

    def create_preset(self, preset_dict):
        try:
            preset = HardwarePreset(**preset_dict)
            preset.update()
            return dict(ok=preset.name)
        except Exception as exc:
            return dict(error="Preset {} creation error: {}".format(exc))

    def get_preset(self, name):
        try:
            preset = HardwarePreset.get(name=name)
            return dict(ok=preset.to_dict())
        except DoesNotExist:
            return dict(error="Preset not found: {}".format(name))
        except Exception as exc:
            return dict(error="Preset {} read error: {}".format(name, exc))

    def update_preset(self, name, preset_dict):
        try:
            preset = HardwarePreset.get(name=name)
            preset.apply(preset_dict)
            preset.update()
            return dict(ok=name)
        except DoesNotExist:
            return dict(error="Preset not found: {}".format(name))
        except Exception as exc:
            return dict(error="Preset {} update error: {}".format(name, exc))

    def remove_preset(self, name):
        try:
            HardwarePreset.delete().where(name=name)
        except DoesNotExist:
            return dict(error="Preset not found: {}".format(name))
        except Exception as exc:
            return dict(error="Preset {} removal error: {}".format(name, exc))

    def activate_preset(self, name):
        raise NotImplementedError
