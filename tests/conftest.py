import os

import pytest

from golem.core.common import is_windows


@pytest.fixture(scope="session", autouse=True)
def docker_toolbox_windows_fixture(*_):
    if is_windows():
        host = os.environ.get('DOCKER_HOST')
        os.environ['DOCKER_HOST'] = host or 'tcp://127.0.0.1:2375'
