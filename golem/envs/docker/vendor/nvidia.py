import re
from typing import Dict, List

# FIXME: move the nvgpu module out of the apps folder
from apps.core import nvgpu


VENDOR = 'NVIDIA'

DEFAULT_DEVICES = ['all']
SPECIAL_DEVICES = {
    'void',  # or empty or unset: the same behavior as runc
    'none',  # no GPUs accessible, but driver capabilities will be enabled
    'all',  # all GPUs accessible
}
DEVICE_INDEX_REGEX = re.compile(r"^(\d+)$")
DEVICE_NAME_REGEX = re.compile(r"^(GPU-[a-fA-F0-9\-]+)$")

DEFAULT_CAPABILITIES = ['compute', 'graphics', 'utility']
SPECIAL_CAPABILITIES = {
    'all',  # enable all available driver capabilities
}
CAPABILITIES = {
    'compute',  # required for CUDA and OpenCL applications
    'compat32',  # required for running 32-bit applications
    'graphics',  # required for running OpenGL and Vulkan applications
    'utility',  # required for using nvidia-smi and NVML
    'video',  # required for using the Video Codec SDK
    'display',  # required for leveraging X11 display
}

DEFAULT_REQUIREMENTS: Dict[str, str] = dict()
REQUIREMENTS = {
    'cuda',  # constraint on the CUDA driver version
    'driver',  # constraint on the driver version
    'arch',  # constraint on the compute architectures of the selected GPUs
    'brand',  # constraint on the brand of the selected GPUs (e.g. GeForce)
}


def is_supported() -> bool:
    return nvgpu.is_supported()


def validate_devices(devices: List[str]) -> None:
    if not devices:
        raise ValueError(f"Missing {VENDOR} GPUs: {devices}")

    special_count = sum([d in SPECIAL_DEVICES for d in devices])
    has_mixed_devices = special_count > 0 and len(devices) > 1

    if special_count > 1 or has_mixed_devices:
        raise ValueError(f"Mixed {VENDOR} GPU devices: {devices}")
    # Only a "special" device name was provided
    if special_count > 0:
        return

    # All device names are device indexes
    if all([DEVICE_INDEX_REGEX.match(d) for d in devices]):
        return
    # All device names are in a form of a UUID
    if all([DEVICE_NAME_REGEX.match(d) for d in devices]):
        return

    raise ValueError(f"Invalid {VENDOR} GPU device names: {devices}")


def validate_capabilities(caps: List[str]) -> None:
    if not caps:
        raise ValueError(f"Missing {VENDOR} GPU caps: {caps}")

    special_count = sum([c in SPECIAL_CAPABILITIES for c in caps])
    has_mixed_caps = special_count > 0 and len(caps) > 1

    if special_count > 1 or has_mixed_caps:
        raise ValueError(f"Mixed {VENDOR} GPU caps: {caps}")
    # Only a "special" capability was provided
    if special_count > 0:
        return

    # All capability names are known
    if not all([c in CAPABILITIES for c in caps]):
        raise ValueError(f"Invalid {VENDOR} GPU caps: {caps}")


def validate_requirements(requirements: Dict[str, str]) -> None:
    """ Validate requirement names and check if a value was provided """
    for name, val in requirements.items():
        if name not in REQUIREMENTS:
            raise ValueError(
                f"Invalid {VENDOR} GPU requirement name: '{name}'")
        if not val:
            raise ValueError(
                f"Invalid {VENDOR} GPU requirement value: '{name}'='{val}'")
