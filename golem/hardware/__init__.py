import logging
import sys
from multiprocessing import cpu_count
from typing import List, Optional, Dict

import psutil
from psutil import virtual_memory

from golem.appconfig import MIN_MEMORY_SIZE, TOTAL_MEMORY_CAP, MIN_CPU_CORES, \
    MIN_DISK_SPACE
from golem.core.common import is_linux, is_osx, is_windows
from golem.core.fileshelper import free_partition_space

logger = logging.getLogger(__name__)

MAX_CPU_WINDOWS = 32
MAX_CPU_MACOS = 16

_working_dir: Optional[str] = None


def initialize(working_dir: str):
    global _working_dir
    _working_dir = working_dir


def caps() -> Dict[str, int]:
    _assert_initialized()

    return {
        'cpu_cores': len(cpus()),
        'memory': memory(),
        'disk': disk(),
    }


def defaults() -> Dict[str, int]:
    return {
        'cpu_cores': len(cpus()),
        'memory': memory(),
        'disk': MIN_DISK_SPACE,
    }


def cap_cpus(core_num: int, cap: int = sys.maxsize) -> int:
    cap = max(cap, MIN_CPU_CORES)
    available = min(cap, len(cpus()))
    return max(min(core_num, available), MIN_CPU_CORES)


def cap_memory(mem_size: int, cap: int = sys.maxsize) -> int:
    cap = max(cap, MIN_MEMORY_SIZE)
    available = min(cap, memory())
    capped = max(min(mem_size, available), MIN_MEMORY_SIZE)
    return _pad_memory(capped)


def cap_disk(disk_space: int, cap: int = sys.maxsize) -> int:
    _assert_initialized()
    cap = max(cap, MIN_DISK_SPACE)
    available = min(cap, disk())
    return max(min(disk_space, available), MIN_DISK_SPACE)


def cpus() -> List[int]:
    """
    Lists CPU cores affined to the process (Linux, Windows) or the available
    core count (macOS). On Linux, tries to remove the first core from the
    list if no custom affinity has been set.
    :return list: A list of CPU cores available for computation.
    """
    core_count = cpu_count()

    try:
        affinity = psutil.Process().cpu_affinity()
    except Exception as e:
        logger.debug("Couldn't read CPU affinity: %r", e)
        affinity = list(range(0, core_count - 1))

    # FIXME: The Linux case will no longer be valid when VM computations are
    #        introduced.
    if is_linux():
        if len(affinity) == core_count and 0 in affinity:
            affinity.remove(0)
    else:
        if is_osx() and len(affinity) > MAX_CPU_MACOS:
            affinity = affinity[:MAX_CPU_MACOS]
        elif is_windows() and len(affinity) > MAX_CPU_WINDOWS:
            affinity = affinity[:MAX_CPU_WINDOWS]
        affinity = list(range(0, len(affinity)))
    return affinity or [0]


def memory() -> int:
    """
    :return int: 3/4 of total memory in KiB
    """
    capped = virtual_memory().total * TOTAL_MEMORY_CAP // 1024
    amount = max(capped, MIN_MEMORY_SIZE)

    logger.debug("Total memory: %r", amount)
    return amount


def memory_available() -> int:
    """
    :return int: available memory in KiB
    """
    vmem = virtual_memory()

    logger.debug("System memory: %r", vmem)
    return vmem.available // 1024


def disk() -> int:
    _assert_initialized()
    return free_partition_space(_working_dir)


def _pad_memory(in_bytes: int) -> int:
    """
    Returns the provided memory amount as a multiple of 2
    """
    return int(in_bytes) & ~1


def _assert_initialized():
    if not _working_dir:
        raise EnvironmentError(f"{__name__} not initialized")
