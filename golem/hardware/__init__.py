import logging
from multiprocessing import cpu_count
from typing import List

import psutil
from psutil import virtual_memory

from golem.appconfig import MIN_MEMORY_SIZE
from golem.core.common import is_linux, is_osx, is_windows

logger = logging.getLogger(__name__)

MAX_CPU_WINDOWS = 32
MAX_CPU_MACOS = 16


def cpu_cores_available() -> List[int]:
    """
    Lists CPU cores affined to the process (Linux, Windows) or the available
    core count (macOS). On Linux, tries to remove the first core from the list
    if no custom affinity has been set.
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


def memory_available() -> int:
    """
    :return int: 3/4 of total available memory in KiB
    """
    return max(int(virtual_memory().total * 0.75 / 1024), MIN_MEMORY_SIZE)
