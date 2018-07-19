from golem import testutils
from golem.appconfig import DEFAULT_HARDWARE_PRESET_NAME as DEFAULT, \
    CUSTOM_HARDWARE_PRESET_NAME as CUSTOM, MIN_MEMORY_SIZE, MIN_DISK_SPACE, \
    MIN_CPU_CORES
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset


class TestHardwarePresets(testutils.DatabaseFixture):

    def setUp(self):
        super().setUp()
        HardwarePresets.initialize(self.tempdir)
        self.config = ClientConfigDescriptor()

    def test_initialize(self):
        assert HardwarePreset.get(name=DEFAULT)
        assert HardwarePreset.get(name=CUSTOM)

    def test_caps(self):
        caps = HardwarePresets.caps()
        assert caps['cpu_cores'] > 0
        assert caps['memory'] > 0
        assert caps['disk'] > 0

    def test_update_config_to_default(self):
        # given
        _, default_preset = HardwarePresets.values(DEFAULT)

        # when
        config_changed = HardwarePresets.update_config(DEFAULT, self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == DEFAULT
        assert self.config.num_cores == default_preset['cpu_cores']
        assert self.config.max_memory_size == default_preset['memory']
        assert self.config.max_resource_size == default_preset['disk']

    def test_update_config_lower_bounds(self):
        # given
        HardwarePreset.create(name='min', cpu_cores=-7, memory=3, disk=2)

        # when
        config_changed = HardwarePresets.update_config('min', self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == 'min'
        assert self.config.num_cores == MIN_CPU_CORES
        assert self.config.max_memory_size == MIN_MEMORY_SIZE
        assert self.config.max_resource_size == MIN_DISK_SPACE

    def test_update_config(self):
        # given
        cpu_cores = 1
        memory = 1200000
        disk = 2000000

        HardwarePreset.create(name='foo', cpu_cores=cpu_cores, memory=memory,
                              disk=disk)

        # when
        config_changed = HardwarePresets.update_config('foo', self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == 'foo'
        assert self.config.num_cores == HardwarePresets.cpu_cores(cpu_cores)
        assert self.config.max_memory_size == HardwarePresets.memory(memory)
        assert self.config.max_resource_size == HardwarePresets.disk(disk)

    def test_update_config_upper_bounds(self):
        # given
        HardwarePreset.create(name='max', cpu_cores=1e9, memory=1e18, disk=1e18)
        caps = HardwarePresets.caps()

        # when
        config_changed = HardwarePresets.update_config('max', self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == 'max'
        assert self.config.num_cores == caps['cpu_cores']
        assert self.config.max_memory_size == caps['memory']
        assert self.config.max_resource_size == caps['disk']

    def test_update_config_not_changed(self):
        # given
        HardwarePreset.create(name='foo', cpu_cores=1, memory=1200000,
                              disk=2000000)

        # then
        assert not HardwarePresets.update_config(DEFAULT, self.config)
        assert not HardwarePresets.update_config(DEFAULT, self.config)
        assert not HardwarePresets.update_config(DEFAULT, self.config)
        assert HardwarePresets.update_config(CUSTOM, self.config)
        assert not HardwarePresets.update_config(CUSTOM, self.config)
        assert HardwarePresets.update_config(DEFAULT, self.config)
        assert HardwarePresets.update_config('foo', self.config)
        assert not HardwarePresets.update_config('foo', self.config)
