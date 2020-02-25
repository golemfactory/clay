import logging
import typing

from golem.rpc import utils as rpc_utils

if typing.TYPE_CHECKING:
    # pylint:disable=unused-import, ungrouped-imports
    from golem.apps.manager import AppManager

logger = logging.getLogger(__name__)


class ClientAppProvider:
    def __init__(self, app_manager: 'AppManager'):
        self.app_manager = app_manager

    @rpc_utils.expose('apps.list')
    def apps_list(self):
        logger.debug('apps.list called from rpc')
        result = []
        for app_id, app_def in self.app_manager.apps():
            logger.debug('app_id=%r, app_def=%r', app_id, app_def)
            app_result = {
                'id': app_id,
                'name': app_def.name,
                'version': app_def.version,
                'enabled': self.app_manager.enabled(app_id),
            }
            # TODO: Add full argument for more values
            result.append(app_result)
        logger.info('Listing apps. count=%r', len(result))
        return result

    @rpc_utils.expose('apps.update')
    def apps_update(self, app_id, enabled):
        logger.debug(
            'apps.update called from rpc. app_id=%r, enabled=%r',
            app_id,
            enabled,
        )
        if not self.app_manager.registered(app_id):
            raise Exception(f"App not found, please check the app_id={app_id}")
        self.app_manager.set_enabled(app_id, bool(enabled))
        logger.info('Updated app. app_id=%r, enabled=%r', app_id, enabled)
        return "App state updated."

    @rpc_utils.expose('apps.delete')
    def apps_delete(self, app_id):
        logger.debug('apps.delete called from rpc. app_id=%r', app_id)
        if not self.app_manager.delete(app_id):
            raise Exception(f"Failed to delete app. app_id={app_id}")
        logger.info('Deleted app. app_id=%r', app_id)
        return "App deleted with success."
