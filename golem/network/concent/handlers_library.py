import logging
import warnings

from collections import Callable

from golem_messages import message


logger = logging.getLogger(__name__)


class DuplicatedHandler(UserWarning):
    pass


class HandlersLibrary():
    """Library of handlers for messages received from concent"""
    __slots__ = ('_handlers', )

    def __init__(self):
        # Messages handlers: msg_cls: handler callable
        self._handlers = {}

    def register_handler(self, msg_cls: message.base.Message) -> Callable:
        def _wrapped(f) -> Callable:
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
