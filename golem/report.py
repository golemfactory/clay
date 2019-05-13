from contextlib import contextmanager
from functools import wraps

from typing import Any, ClassVar, Dict, Optional, Tuple

from twisted.internet.defer import Deferred, maybeDeferred

from golem.rpc.session import Publisher
from golem.rpc.mapping.rpceventnames import Golem


class Stage(object):
    """
    Method execution stages.
    """
    pre = 'pre'
    post = 'post'
    warning = 'warning'
    exception = 'exception'


class Component(object):
    """
    Predefined components of the application.
    """
    client = 'client'
    docker = 'docker'
    hypervisor = 'hypervisor'
    ethereum = 'ethereum'
    hyperdrive = 'hyperdrive'


class StatusPublisher(object):
    """
    Publishes method execution stages via RPC.
    """
    _initialized: ClassVar[bool] = False
    _rpc_publisher: ClassVar[Optional[Publisher]] = None
    _last_status: ClassVar[Dict[str, Tuple[str, str, Any]]] = dict()

    @classmethod
    def publish(cls, component, method, stage, data=None) -> Optional[Deferred]:
        """
        Convenience function for publishing the execution stage event.

        :param component: Component name
        :param method: Method name
        :param stage: Execution stage to report at: pre, post (defined in
        golem.report.Stage). Exceptions are always reported. If not specified,
        both 'pre' and 'post' are used.
        :param data: Payload (optional)
        :return: None if there's no rpc publisher; deferred
                 autobahn.wamp.request.Publication on success or None if
                 session is closing or there was an error
        """
        cls._update_status(component, method, stage, data)

        if cls._rpc_publisher:
            from twisted.internet import reactor
            deferred = Deferred()

            def _publish():
                maybeDeferred(
                    cls._rpc_publisher.publish,
                    Golem.evt_golem_status,
                    cls._last_status
                ).chainDeferred(deferred)

            reactor.callFromThread(_publish)
            return deferred
        return None

    @classmethod
    def last_status(cls):
        return cls._last_status

    @classmethod
    def initialize(cls, rpc_publisher):
        if cls._initialized:
            return

        from pydispatch import dispatcher
        dispatcher.connect(cls._publish_listener,
                           signal=Golem.evt_golem_status)

        cls._rpc_publisher = rpc_publisher
        cls._initialized = True

    @classmethod
    def _publish_listener(cls, event: str = 'default', **kwargs) -> None:
        if event != 'publish':
            return

        cls.publish(kwargs['component'],
                    kwargs['method'],
                    kwargs['stage'],
                    kwargs.get('data'))

    @classmethod
    def _update_status(cls, component, method, stage, data) -> None:
        if data and not isinstance(data, dict):
            data = {"status": "message", "value": data}
        cls._last_status[component] = (method, stage, data)


@contextmanager
def report_call(component, method, stage=None):
    """
    Context manager for reporting method / block execution stages via RPC.

    :param component: Component name
    :param method: Method name
    :param stage: Execution stage to report at: pre, post (defined in
    golem.report.Stage). Exceptions are always reported. If not specified,
    both 'pre' and 'post' are used.
    :return: None
    """

    # Publish a pre-execution event
    if not stage or stage == Stage.pre:
        StatusPublisher.publish(component, method, Stage.pre)
    try:
        yield
    except BaseException as e:
        # Publish and re-raise exceptions
        StatusPublisher.publish(component, method, Stage.exception, str(e))
        raise
    else:
        # Publish a post-execution event
        if not stage or stage == Stage.post:
            StatusPublisher.publish(component, method, Stage.post)


def report_calls(component, method, stage=None, once=False):
    """
    Function decorator for reporting method execution stages via the
    report_call context manager.

    :param component: Component name
    :param method: Method name
    :param stage: Execution stage to report at: pre, post (defined in
    golem.report.Stage). Exceptions are always reported. If not specified,
    both 'pre' and 'post' are used.
    :param once: Whether to report execution once
    :return: Function decorator
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # If executing once, set a unique flag in the function object
            if once:
                prop = '_report_called_{}'.format(method)
                if hasattr(func, prop):
                    return func(*args, **kwargs)
                setattr(func, prop, True)
            # Use the context manager to report the execution stage
            with report_call(component, method, stage):
                return func(*args, **kwargs)
        return wrapper
    return decorator
