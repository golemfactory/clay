import inspect
import logging

from golem_messages import message

from golem.task import taskserver

from golem.network.concent import helpers as concent_helpers
from golem.network.concent.handlers_library import library

logger = logging.getLogger(__name__)


class TaskServerMessageHandler():
    """Container for received message handlers that require TaskServer."""
    def __init__(self, task_server: taskserver.TaskServer):
        self.task_server = task_server
        self.register_handlers()

    def register_handlers(self) -> None:
        for method in inspect.getmembers(self, inspect.ismethod):
            try:
                msg_cls = method.handler_for
            except AttributeError:
                continue
            library.register_handler(msg_cls)(method)

    def on_concents_service_refused(self, msg):
        self.task_server.concent_refused(
            subtask_id=msg.subtask_id,
            reason=msg.reason,
        )
    on_concents_service_refused.handler_for = message.concents.ServiceRefused

    def on_concents_force_report_computed_task(self, msg):
        concent_helpers.process_report_computed_task(
            msg=msg.report_computed_task,
            task_session=None,
        )
        # FIXME move all logic from session._react_to_report.. to taskserver
        self.task_server.ack_report_computed_task(msg.report_computed_task)
    on_concents_force_report_computed_task.handler_for = \
        message.concents.ForceReportComputedTask
