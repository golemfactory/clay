
import pytest


def pytest_runtest_makereport(item, call):
    if "incremental" in item.keywords:
        if call.excinfo is not None:
            parent = item.parent
            parent._previousfailed = item


def pytest_runtest_setup(item):
    if "incremental" in item.keywords:
        previousfailed = getattr(item.parent, "_previousfailed", None)
        if previousfailed is not None:
            pytest.xfail("previous test failed (%s)" % previousfailed.name)


def pytest_addoption(parser):
    parser.addoption("--master", action="store", default="http://10.30.10.201:4545",
        help="url to master")

    parser.addoption("--branch", action="store", default="b0.16.1")

    parser.addoption("--golemversion", action="store", default="0.16.1")


def pytest_generate_tests(metafunc):
    if 'master' in metafunc.fixturenames:
        metafunc.parametrize("master",
                             metafunc.config.getoption('master'))