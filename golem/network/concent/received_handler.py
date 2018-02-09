import inspect
import logging
import warnings

from golem_messages import message

from golem.task import taskserver

from golem.network.concent import helpers as concent_helpers

logger = logging.getLogger(__name__)


class DuplicatedHandler(UserWarning):
    pass


class HandlersLibrary():
    """Library of handlers for messages received from concent"""
    __slots__ = ('_handlers', )

    def __init__(self):
        # Messages handlers: msg_cls: handler callable
        self._handlers = {}

    def register_handler(self, msg_cls: message.base.Message) -> None:
        def _wrapped(f):
            if msg_cls in self._handlers:
                warnings.warn(
                    "Duplicated handler for {msg_cls}."
                    " Replacing {current_handler} with {new_handler}".format(
                        msg_cls=msg_cls.__name__,
                        current_handler=self._handlers[msg_cls],
                        new_handler=f,
                    ),
                    DuplicatedHandler,
                )
            self._handlers[msg_cls] = f
            return f
        return _wrapped

    def interpret(self, msg) -> None:
        try:
            handler = self._handlers[msg.__class__]
        except KeyError:
            logger.warning(
                "I don't know how to handle %s. Ignoring %r",
                msg.__class__,
                msg,
            )
            return
        handler(msg)


# The only reference to HandlersLibrary that should be used
library = HandlersLibrary()


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
