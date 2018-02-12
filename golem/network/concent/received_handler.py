import inspect
import logging

from golem_messages import message

from golem.task import taskserver

from golem.network.concent import helpers as concent_helpers
from golem.network.concent.handlers_library import library

logger = logging.getLogger(__name__)


def handler_for(msg_cls: message.base.Message):
    def wrapped(f):
        f.handler_for = msg_cls
        return f
    return wrapped


def register_handlers(instance) -> None:
    for _, method in inspect.getmembers(instance, inspect.ismethod):
        try:
            msg_cls = method.handler_for
        except AttributeError:
            continue
        library.register_handler(msg_cls)(method)


class TaskServerMessageHandler():
    """Container for received message handlers that require TaskServer."""
    def __init__(self, task_server: taskserver.TaskServer):
        self.task_server = task_server
        register_handlers(self)

    @handler_for(message.concents.ServiceRefused)
    def on_concents_service_refused(self, msg):
        self.task_server.concent_refused(
            subtask_id=msg.subtask_id,
            reason=msg.reason,
        )

    # REMOVE AFTER gm116 pylint: disable=no-self-use
    @handler_for(message.concents.ForceReportComputedTask)
    def on_concents_force_report_computed_task(self, msg):
        concent_helpers.process_report_computed_task(
            msg=msg.task_to_compute,
            task_session=None,
        )
        # FIXME implement after
        # https://github.com/golemfactory/golem-messages/issues/116
    # REMOVE AFTER gm116 pylint: enable=no-self-use
