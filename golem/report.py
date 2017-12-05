from contextlib import contextmanager
from functools import wraps

from golem.core.common import to_unicode
from golem.rpc.mapping.rpceventnames import Golem


class Stage(object):
    """
    Method execution stages.
    """
    pre = 'pre'
    post = 'post'
    exception = 'exception'


class Component(object):
    """
    Predefined components of the application.
    """
    client = 'client'
    docker = 'docker'
    hypervisor = 'hypervisor'
    ethereum = 'ethereum'


class StatusPublisher(object):
    """
    Publishes method execution stages via RPC.
    """
    _rpc_publisher = None
    _last_status = None

    @classmethod
    def publish(cls, component, method, stage, data=None):
        """
        Convenience function for publishing the execution stage event.

        :param component: Component name
        :param method: Method name
        :param stage: Execution stage to report at: pre, post (defined in
        golem.report.Stage). Exceptions are always reported. If not specified,
        both 'pre' and 'post' are used.
        :param data: Payload (optional)
        :return: None
        """
        if cls._rpc_publisher:
            cls._last_status = (to_unicode(component),
                                to_unicode(method),
                                to_unicode(stage),
                                data)

            cls._rpc_publisher.publish(Golem.evt_golem_status,
                                       *cls._last_status)

    @classmethod
    def last_status(cls):
        return cls._last_status

    @classmethod
    def set_publisher(cls, rpc_publisher):
        cls._rpc_publisher = rpc_publisher


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
