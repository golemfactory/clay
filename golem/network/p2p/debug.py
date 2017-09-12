from devp2p import slogging
from devp2p.service import WiredService

logger = slogging.get_logger('devp2p')
log_func = logger.info


def _decorate(func, prefix):

    def wrapper(*args, **kwargs):
        proto = args[0]
        ip, port = proto.peer.ip_port
        log_func('{}:{} {} {} ({}, {})'.format(ip, port, prefix, func.__name__,
                                               args[1:], kwargs))
        return func(*args, **kwargs)

    return wrapper


def _log_calls(service, like, prefix):
    assert isinstance(service, WiredService)

    methods = [getattr(service, m) for m in dir(service)
               if callable(getattr(service, m, None)) and m.startswith(like)]

    for method in methods:
        setattr(service, method.__name__, _decorate(method, prefix))


def log_receive(service):
    _log_calls(service, 'receive_', prefix='R->')


def log_send(service):
    _log_calls(service, 'send_', prefix='<-S')


def log_all(proto):
    log_receive(proto)
    log_send(proto)
