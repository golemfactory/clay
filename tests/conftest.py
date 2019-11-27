import os
from unittest import mock

from pydispatch import dispatcher
import pytest

from golem.core.common import is_windows


@pytest.fixture(scope="session", autouse=True)
def docker_toolbox_windows_fixture(*_):
    if is_windows():
        host = os.environ.get('DOCKER_HOST')
        os.environ['DOCKER_HOST'] = host or 'tcp://127.0.0.1:2375'


@pytest.fixture(scope="session", autouse=True)
def disable_benchmarks(request):
    ctx = mock.patch('golem.task.benchmarkmanager.BenchmarkManager.'
                     'benchmarks_needed', return_value=False)

    ctx.__enter__()
    request.addfinalizer(ctx.__exit__)


@pytest.fixture(scope="function", autouse=True)
def clean_task_api_ssl_context_config(request):
    ctx = mock.patch(
        'golem.apps.ssl.SSLContextConfig',
        mock.Mock(key_and_cert_directory=None))
    ctx.__enter__()
    request.addfinalizer(ctx.__exit__)


@pytest.fixture(autouse=True)
def clean_dispatcher():
    """
    Dispatcher is a global object shared between different tests so it may
    happen that one tests subscribes to a signal than some completely different
    tests sends this signal triggering code from the first test which is
    completely unexpected and undefined.
    """
    yield
    dispatcher.connections = {}
    dispatcher.senders = {}
    dispatcher.sendersBack = {}
