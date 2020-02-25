import pytest
from mock import Mock

from golem.apps.rpc import ClientAppProvider
from golem.apps.manager import AppManager
from golem.apps.default import BlenderAppDefinition
from golem.testutils import pytest_database_fixture  # noqa pylint: disable=unused-import


class TestClientAppProvider:
    @pytest.fixture(autouse=True)
    def setup_method(self):
        self._app_manger = Mock(spec=AppManager)
        self._handler = ClientAppProvider(self._app_manger)

    def test_list(self):
        # given
        mocked_apps = [(BlenderAppDefinition.id, BlenderAppDefinition)]
        self._app_manger.apps = Mock(
            return_value=mocked_apps
        )

        # when
        result = self._handler.apps_list()

        # then
        assert len(result) == len(mocked_apps), \
            'count of result does not match input count'
        assert result[0]['id'] == mocked_apps[0][0], \
            'the first returned app id does not match input'
        assert self._app_manger.apps.called_once_with()

    def test_update(self):
        # given
        app_id = 'a'
        enabled = True

        # when
        result = self._handler.apps_update(app_id, enabled)

        # then
        self._app_manger.registered.called_once_with(app_id)
        self._app_manger.set_enabled.called_once_with(app_id, enabled)
        assert result == 'App state updated.'

    def test_update_not_registered(self):
        # given
        app_id = 'a'
        enabled = True
        self._app_manger.registered.return_value = False

        # when
        with pytest.raises(Exception):
            self._handler.apps_update(app_id, enabled)

        # then
        self._app_manger.registered.called_once_with(app_id)
        self._app_manger.set_enabled.assert_not_called()

    def test_delete(self):
        # given
        app_id = 'a'

        # when
        result = self._handler.apps_delete(app_id)

        # then
        self._app_manger.delete.called_once_with(app_id)
        assert result == 'App deleted with success.'

    def test_delete_failed(self):
        # given
        app_id = 'a'
        self._app_manger.delete.return_value = False

        # when
        with pytest.raises(Exception):
            self._handler.apps_delete(app_id)

        # then
        self._app_manger.delete.called_once_with(app_id)
