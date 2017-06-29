from contextlib import contextmanager
from functools import wraps

from golem.core.common import to_unicode
from golem.rpc.mapping.aliases import Golem


class Stage(object):
    pre = 'pre'
    post = 'post'
    exception = 'exception'


class Component(object):
    client = 'client'
    docker = 'docker'
    hypervisor = 'hypervisor'
    ethereum = 'ethereum'


class StatePublisher(object):
    _rpc_publisher = None

    @classmethod
    def publish(cls, component, part, stage, data=None):
        if cls._rpc_publisher:
            cls._rpc_publisher.publish(Golem.evt_component_state,
                                       to_unicode(component),
                                       to_unicode(part),
                                       to_unicode(stage),
                                       data)

    @classmethod
    def set_publisher(cls, rpc_publisher):
        cls._rpc_publisher = rpc_publisher


@contextmanager
def report_call(component, part, stage=None):
    if not stage or stage == Stage.pre:
        StatePublisher.publish(component, part, Stage.pre)
    try:
        yield
    except Exception as e:
        StatePublisher.publish(component, part, Stage.exception, unicode(e))
        raise
    else:
        if not stage or stage == Stage.post:
            StatePublisher.publish(component, part, Stage.post)


def report_calls(component, part, stage=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with report_call(component, part, stage):
                return func(*args, **kwargs)
        return wrapper
    return decorator
