import json
import pytest
from mock import patch
from functools import partial
from unittest import mock
from golem.version import check_update, Importance

importance = Importance()

# This method will be used by the mock to replace requests.get
def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    if args[0] == "fail":
        return MockResponse(None, 404)
    return MockResponse([{"tag_name": "0.8.1"}], 200)
    

@mock.patch('requests.get', side_effect=mocked_requests_get)
@patch('golem.version.APP_VERSION', "0.8.1")
def test_updated():
    try:
        assert isinstance(check_update(), bool)
    except Exception:
        pytest.fail("Unexpected error ..")

@mock.patch('requests.get', side_effect=mocked_requests_get)
@patch('golem.version.APP_VERSION', "0.8.0")
def test_outdated_patch():
    try:
        result = check_update()
        assert isinstance(result, object)
        result = json.loads(result)
        assert result['importance'] == importance.PATCH
    except Exception:
        pytest.fail("Unexpected error ..")

@mock.patch('requests.get', side_effect=mocked_requests_get)
@patch('golem.version.APP_VERSION', "0.7.0")
def test_outdated_minor():
    try:
        result = check_update()
        assert isinstance(result, object)
        result = json.loads(result)
        assert result['importance'] == importance.MINOR
    except Exception:
        pytest.fail("Unexpected error ..")

@mock.patch('requests.get', side_effect=partial(mocked_requests_get, "fail"))
@patch('golem.version.APP_VERSION', "0.8.1")
def test_failed():
    with pytest.raises(Exception):
        check_update()
