from golem import testutils
from golem.appconfig import DEFAULT_HARDWARE_PRESET_NAME, \
    CUSTOM_HARDWARE_PRESET_NAME, MIN_MEMORY_SIZE, MIN_DISK_SPACE, MIN_CPU_CORES
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset


class TestHardwarePresets(testutils.DatabaseFixture):

    def setUp(self):
        super().setUp()
        HardwarePresets.initialize(self.tempdir)
        self.config = ClientConfigDescriptor()

    def test_initialize(self):
        assert HardwarePreset.get(name=DEFAULT_HARDWARE_PRESET_NAME)
        assert HardwarePreset.get(name=CUSTOM_HARDWARE_PRESET_NAME)

    def test_caps(self):
        caps = HardwarePresets.caps()
        assert caps['cpu_cores'] > 0
        assert caps['memory'] > 0
        assert caps['disk'] > 0

    def test_update_config_to_default(self):
        # given
        _, default_preset = HardwarePresets.values(DEFAULT_HARDWARE_PRESET_NAME)

        # when
        config_changed = HardwarePresets.update_config(
            DEFAULT_HARDWARE_PRESET_NAME, self.config)

        # then
        assert config_changed
        assert self.config.hardware_preset_name == DEFAULT_HARDWARE_PRESET_NAME
        assert self.config.num_cores == default_preset['cpu_cores']
        assert self.config.max_memory_size == default_preset['memory']
        assert self.config.max_resource_size == default_preset['disk']

    def test_update_config_lower_bounds(self):
        # given
        HardwarePreset.create(name='min', cpu_cores=-7, memory=3, disk=2)

        # when
        config_changed = HardwarePresets.update_config('min', self.config)

        # then
        assert config_changed
        assert self.config.hardware_preset_name == 'min'
        assert self.config.num_cores == MIN_CPU_CORES
        assert self.config.max_memory_size == MIN_MEMORY_SIZE
        assert self.config.max_resource_size == MIN_DISK_SPACE

    def test_update_config(self):
        # given
        HardwarePreset.create(name='foo', cpu_cores=1, memory=1200000,
                              disk=2000000)

        # when
        config_changed = HardwarePresets.update_config('foo', self.config)

        # then
        assert config_changed
        assert self.config.hardware_preset_name == 'foo'
        assert self.config.num_cores == 1
        assert self.config.max_memory_size == 1200000
        assert self.config.max_resource_size == 2000000

    def test_update_config_upper_bounds(self):
        # given
        HardwarePreset.create(name='max', cpu_cores=1e9, memory=1e18, disk=1e18)
        caps = HardwarePresets.caps()

        # when
        config_changed = HardwarePresets.update_config('max', self.config)

        # then
        assert config_changed
        assert self.config.hardware_preset_name == 'max'
        assert self.config.num_cores == caps['cpu_cores']
        assert self.config.max_memory_size == caps['memory']
        assert self.config.max_resource_size == caps['disk']

    def test_update_config_not_changed(self):
        assert HardwarePresets.update_config(
            DEFAULT_HARDWARE_PRESET_NAME, self.config)
        assert not HardwarePresets.update_config(
            DEFAULT_HARDWARE_PRESET_NAME, self.config)
        assert not HardwarePresets.update_config(
            DEFAULT_HARDWARE_PRESET_NAME, self.config)
        assert HardwarePresets.update_config(
            CUSTOM_HARDWARE_PRESET_NAME, self.config)
        assert not HardwarePresets.update_config(
            CUSTOM_HARDWARE_PRESET_NAME, self.config)
