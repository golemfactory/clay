import uuid

from peewee import DoesNotExist, IntegrityError
from twisted.python.failure import Failure

from golem.appconfig import DEFAULT_HARDWARE_PRESET_NAME, CUSTOM_HARDWARE_PRESET_NAME
from golem.config.presets import HardwarePresetsMixin
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset
from golem.tools.testwithdatabase import TestWithDatabase


class TestHardwarePresetsMixin(TestWithDatabase):

    def setUp(self):
        super(TestHardwarePresetsMixin, self).setUp()
        HardwarePresets.initialize(self.tempdir)

    def test_get_hw_caps(self):
        caps = HardwarePresetsMixin.get_hw_caps()
        assert caps['cpu_cores'] >= 1
        assert caps['memory'] > 0
        assert caps['disk'] > 0

    def test_get_hw_presets(self):
        presets = HardwarePresetsMixin.get_hw_presets()
        assert len(presets) >= 2
        assert all([preset is not None for preset in presets])

    def test_get_hw_preset(self):
        assert HardwarePresetsMixin.get_hw_preset(DEFAULT_HARDWARE_PRESET_NAME)
        assert HardwarePresetsMixin.get_hw_preset(CUSTOM_HARDWARE_PRESET_NAME)

        with self.assertRaises(DoesNotExist):
            assert not HardwarePresetsMixin.get_hw_preset(str(uuid.uuid4()))

    def test_create_hw_preset(self):
        preset_name = str(uuid.uuid4())
        preset_cpu_cores = 1
        preset_memory = 1000 * 1024
        preset_disk = 1000 * 1024
        preset_dict = dict()

        def assert_integrity_error(_evt):
            _evt.wait()
            assert isinstance(_evt.result, Failure)
            assert isinstance(_evt.result.value, IntegrityError)

        # try to persist a preset with null values
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_integrity_error(evt)

        preset_dict['name'] = preset_name
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_integrity_error(evt)

        preset_dict['cpu_cores'] = preset_cpu_cores
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_integrity_error(evt)

        preset_dict['memory'] = preset_memory
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_integrity_error(evt)

        # persist a preset with all values set
        preset_dict['disk'] = preset_disk
        HardwarePresetsMixin.create_hw_preset(preset_dict).wait()
        preset = HardwarePresetsMixin.get_hw_preset(preset_name)

        # try to insert a preset with the same name
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_integrity_error(evt)

        assert preset
        assert preset['name'] == preset_name
        assert preset['cpu_cores'] == preset_cpu_cores
        assert preset['memory'] == preset_memory
        assert preset['disk'] == preset_disk

        # use upsert to create a preset from dict
        preset_dict['name'] = str(uuid.uuid4())
        HardwarePresetsMixin.upsert_hw_preset(preset_dict).wait()
        assert HardwarePresetsMixin.get_hw_preset(preset_dict['name'])

        # use upsert to create a preset from object
        preset_dict['name'] = str(uuid.uuid4())
        preset = HardwarePreset(**preset_dict)
        HardwarePresetsMixin.upsert_hw_preset(preset).wait()
        assert HardwarePresetsMixin.get_hw_preset(preset_dict['name'])

    def test_update_hw_preset(self):

        def assert_success(_evt):
            _evt.wait()
            assert _evt.result
            assert not isinstance(_evt.result, Failure)

        preset_dict = HardwarePresetsMixin.get_hw_caps()
        preset_dict['name'] = str(uuid.uuid4())
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict)
        assert_success(evt)

        preset_dict['cpu_cores'] += 1
        evt = HardwarePresetsMixin.update_hw_preset(preset_dict)
        assert_success(evt)

        preset = HardwarePresetsMixin.get_hw_preset(preset_dict['name'])
        assert preset['cpu_cores'] == preset_dict['cpu_cores']

        preset_dict['cpu_cores'] += 1

        # use upsert to update the preset
        HardwarePresetsMixin.upsert_hw_preset(preset_dict).wait()
        preset = HardwarePresetsMixin.get_hw_preset(preset_dict['name'])
        assert preset['cpu_cores'] == preset_dict['cpu_cores']

    def test_delete_hw_preset(self):
        # do not allow removal of default and custom presets
        with self.assertRaises(ValueError):
            HardwarePresetsMixin.delete_hw_preset(DEFAULT_HARDWARE_PRESET_NAME)
        with self.assertRaises(ValueError):
            HardwarePresetsMixin.delete_hw_preset(CUSTOM_HARDWARE_PRESET_NAME)
        # test removal of a non-existing preset
        evt = HardwarePresetsMixin.delete_hw_preset(str(uuid.uuid4())).wait()
        assert evt.result == 0

        preset_dict = HardwarePresetsMixin.get_hw_caps()
        preset_dict['name'] = str(uuid.uuid4())

        # create and remove a preset
        evt = HardwarePresetsMixin.create_hw_preset(preset_dict).wait()
        assert evt.result

        evt = HardwarePresetsMixin.delete_hw_preset(
            preset_dict['name']).wait()
        assert evt.result

        # make sure that preset does not exist
        evt = HardwarePresetsMixin.delete_hw_preset(
            preset_dict['name']).wait()
        assert evt.result == 0

    def test_sanitize_preset_name(self):
        sanitize = HardwarePresetsMixin._HardwarePresetsMixin__sanitize_preset_name

        assert sanitize(None) == CUSTOM_HARDWARE_PRESET_NAME
        assert sanitize('') == CUSTOM_HARDWARE_PRESET_NAME
        assert sanitize(DEFAULT_HARDWARE_PRESET_NAME) == CUSTOM_HARDWARE_PRESET_NAME
        assert sanitize(CUSTOM_HARDWARE_PRESET_NAME) == CUSTOM_HARDWARE_PRESET_NAME
        assert sanitize('test') == 'test'

    def test_activate_hw_preset(self):
        mixin = HardwarePresetsMixin()
        with self.assertRaises(NotImplementedError):
            mixin.activate_hw_preset('any')
