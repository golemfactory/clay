from unittest.mock import patch

from golem import testutils
from golem.appconfig import DEFAULT_HARDWARE_PRESET_NAME as DEFAULT, \
    CUSTOM_HARDWARE_PRESET_NAME as CUSTOM, MIN_MEMORY_SIZE, MIN_DISK_SPACE, \
    MIN_CPU_CORES
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.core.hardware import HardwarePresets
from golem.model import HardwarePreset


@patch('golem.core.hardware.cpu_cores_available', return_value=[1] * 7)
@patch('golem.core.hardware.memory_available', return_value=7e7)
@patch('golem.core.hardware.free_partition_space', return_value=7e9)
class TestHardwarePresets(testutils.DatabaseFixture):

    def setUp(self):
        super().setUp()
        with patch('golem.core.hardware.free_partition_space',
                   return_value=7e9):
            HardwarePresets.initialize(self.tempdir)
        self.config = ClientConfigDescriptor()

    def test_initialize(self, *_):
        assert HardwarePreset.get(name=DEFAULT)
        assert HardwarePreset.get(name=CUSTOM)

    def test_caps(self, *_):
        caps = HardwarePresets.caps()
        assert caps['cpu_cores'] == 7
        assert caps['memory'] == 7e7
        assert caps['disk'] == 7e9

    def test_cpu_cores(self, *_):
        assert HardwarePresets.cpu_cores(-1) == MIN_CPU_CORES
        assert HardwarePresets.cpu_cores(0) == MIN_CPU_CORES
        assert HardwarePresets.cpu_cores(1) == 1
        assert HardwarePresets.cpu_cores(7) == 7
        assert HardwarePresets.cpu_cores(8) == 7
        assert HardwarePresets.cpu_cores(1e9) == 7

    def test_memory(self, *_):
        assert HardwarePresets.memory(-1) == MIN_MEMORY_SIZE
        assert HardwarePresets.memory(1e6) == MIN_MEMORY_SIZE
        assert HardwarePresets.memory(2 ** 20) == 2 ** 20
        assert HardwarePresets.memory(1e7) == 1e7
        assert HardwarePresets.memory(7e7) == 7e7
        assert HardwarePresets.memory(9e9) == 7e7

    def test_disk(self, *_):
        assert HardwarePresets.disk(-1) == MIN_DISK_SPACE
        assert HardwarePresets.disk(1e6) == MIN_DISK_SPACE
        assert HardwarePresets.disk(2 ** 20) == 2 ** 20
        assert HardwarePresets.disk(1e7) == 1e7
        assert HardwarePresets.disk(7e9) == 7e9
        assert HardwarePresets.disk(9e19) == 7e9

    def test_update_config_to_default(self, *_):
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

    def test_update_config_lower_bounds(self, *_):
        # given
        HardwarePreset.create(name='min', cpu_cores=-7, memory=-1, disk=-1)

        # when
        config_changed = HardwarePresets.update_config('min', self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == 'min'
        assert self.config.num_cores == MIN_CPU_CORES
        assert self.config.max_memory_size == MIN_MEMORY_SIZE
        assert self.config.max_resource_size == MIN_DISK_SPACE

    def test_update_config(self, *_):
        # given
        HardwarePreset.create(name='foo', cpu_cores=1, memory=1200000,
                              disk=2000000)

        # when
        config_changed = HardwarePresets.update_config('foo', self.config)

        # then
        assert not config_changed
        assert self.config.hardware_preset_name == 'foo'
        assert self.config.num_cores == 1
        assert self.config.max_memory_size == 1200000
        assert self.config.max_resource_size == 2000000

    def test_update_config_upper_bounds(self, *_):
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

    def test_update_config_not_changed(self, *_):
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

    def test_update_config_changed_on_env_change(self, *_):
        # given
        HardwarePreset.create(name='foo', cpu_cores=1, memory=1200000,
                              disk=2000000)

        # then
        assert self.config.max_resource_size == 0  # initial
        assert not HardwarePresets.update_config(DEFAULT, self.config)
        assert self.config.max_resource_size == 7e9
        assert not HardwarePresets.update_config(DEFAULT, self.config)
        assert not HardwarePresets.update_config(DEFAULT, self.config)

        # when env changes (disk space shrinks)
        with patch('golem.core.hardware.free_partition_space',
                   return_value=5e9):
            # then
            assert HardwarePresets.update_config(DEFAULT, self.config)
            assert self.config.max_resource_size == 5e9
            assert not HardwarePresets.update_config(DEFAULT, self.config)

        # when env changes again (back to previous state) than
        assert HardwarePresets.update_config(DEFAULT, self.config)
        assert self.config.max_resource_size == 7e9
        assert not HardwarePresets.update_config(DEFAULT, self.config)
