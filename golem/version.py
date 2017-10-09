import requests
import json
import logging
from semantic_version import Version
from golem.core.variables import APP_VERSION
from golem.utils import OrderedClassMembers

log = logging.getLogger("golem.version")


class Importance(metaclass=OrderedClassMembers):
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    PATCH = "PATCH"

# To prove if we're getting latest version number from github
# we're sorting version numbers
# instead of trusting github json ordered by version number.

def max_version(version_list):
    latest_version = "0.0.0"
    for version in version_list:
        version_number = version['tag_name']
        if Version(version_number, partial=True) > Version(latest_version, partial=True):
            latest_version = version_number
    return latest_version


# If the current version is latest one, just returned boolean
# instead of sending json message about it, and we're checking the type
# on client-side if message is boolean or not.

def check_update():
    GITHUB_RELEASE_URL = "https://api.github.com/repos/golemfactory/golem/releases"
    response = requests.get(GITHUB_RELEASE_URL)

    if response.status_code != 200:
        log.error("Github release check error code {}".format(
            response.status_code))
        response.raise_for_status()

    latest_release = max_version(response.json())
    latest_version = Version(latest_release, partial=True)
    current_version = Version(APP_VERSION, partial=True)

    if latest_version > current_version:
        level = [i for i in range(len(list(latest_version))) if list(latest_version)[
            i] != list(current_version)[i]]
        return json.dumps({'version': latest_release, 'importance': Importance.__ordered__[level[0]]})

    return True
