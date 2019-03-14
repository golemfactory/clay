import copy
import logging
import os


logger = logging.getLogger(__name__)


def get_resources_for_task(resources):
    dir_name = get_resources_root_dir(resources)

    if os.path.exists(dir_name):
        return copy.copy(resources)

    return None


def get_resources_root_dir(resources):
    resources = list(resources)
    prefix = os.path.commonprefix(resources)
    return os.path.dirname(prefix)
