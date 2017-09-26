import os
import pytest


@pytest.fixture(scope="session", autouse=True)
def tulipcore_gevent_loop(request):
    os.environ['GEVENT_LOOP'] = 'tulipcore.Loop'
