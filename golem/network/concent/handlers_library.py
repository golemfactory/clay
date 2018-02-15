import inspect
import logging
# import typing
import warnings
import weakref

from collections import Callable

from golem_messages import message


logger = logging.getLogger(__name__)


class DuplicatedHandler(UserWarning):
    pass


class HandlersLibrary():
    """Library of handlers for messages received from concent"""
    __slots__ = ('_handlers', )

    def __init__(self) -> None:
        # Messages handlers: msg_cls: weakref of handler callable
        # Can't use weakref.WeakValueDictionary() because it doesn't work
        # with methods.

        # Once in python3.6:
        #: typing.Dict[message.base.Message, weakref.ref]
        self._handlers = {}

    def register_handler(self, msg_cls: message.base.Message) -> Callable:
        def _wrapped(f) -> Callable:
            try:
                if self._handlers[msg_cls]() is not None:
                    warnings.warn(
                        "Duplicated handler for {msg_cls}."
                        " Replacing {current_handler}"
                        " with {new_handler}".format(
                            msg_cls=msg_cls.__name__,
                            current_handler=self._handlers[msg_cls](),
                            new_handler=f,
                        ),
                        DuplicatedHandler,
                    )
            except KeyError:
                pass

            # Enable mypy quirk once in python3.6
            # ref: typing.Optional[weakref.ref] = None

            # It check wheter f is boundmethod not method/class function
            if inspect.ismethod(f):
                ref = weakref.WeakMethod(f)
            else:
                ref = weakref.ref(f)
            self._handlers[msg_cls] = ref
            return f
        return _wrapped

    def interpret(self, msg) -> None:
        try:
            ref = self._handlers[msg.__class__]
            handler = ref()
            if handler is None:
                raise KeyError(
                    "Handler was defined but it has been garbage collected"
                )
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
