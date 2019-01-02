from unittest.mock import patch

from golem import hardware
from golem.appconfig import MIN_CPU_CORES, MIN_DISK_SPACE, \
    MIN_MEMORY_SIZE
from golem.testutils import TempDirFixture


@patch('golem.hardware.cpus', return_value=[1] * 7)
@patch('golem.hardware.memory', return_value=7e7)
@patch('golem.hardware.disk', return_value=7e9)
class TestHardware(TempDirFixture):

    def test_caps(self, *_):
        hardware.initialize(self.tempdir)
        caps = hardware.caps()
        assert caps['cpu_cores'] == 7
        assert caps['memory'] == 7e7
        assert caps['disk'] == 7e9

    def test_cpu_cores(self, *_):
        assert hardware.cap_cpus(-1) == MIN_CPU_CORES
        assert hardware.cap_cpus(0) == MIN_CPU_CORES
        assert hardware.cap_cpus(1) == 1
        assert hardware.cap_cpus(7) == 7
        assert hardware.cap_cpus(8) == 7
        assert hardware.cap_cpus(1e9) == 7

    def test_memory(self, *_):
        assert hardware.cap_memory(-1) == MIN_MEMORY_SIZE
        assert hardware.cap_memory(1e6) == MIN_MEMORY_SIZE
        assert hardware.cap_memory(2 ** 20) == 2 ** 20
        assert hardware.cap_memory(1e7) == 1e7
        assert hardware.cap_memory(7e7) == 7e7
        assert hardware.cap_memory(9e9) == 7e7

    def test_disk(self, *_):
        hardware.initialize(self.tempdir)
        assert hardware.cap_disk(-1) == MIN_DISK_SPACE
        assert hardware.cap_disk(1e6) == MIN_DISK_SPACE
        assert hardware.cap_disk(2 ** 20) == 2 ** 20
        assert hardware.cap_disk(1e7) == 1e7
        assert hardware.cap_disk(7e9) == 7e9
        assert hardware.cap_disk(9e19) == 7e9
