import abc

import jsonpickle as json
import logging
from pprint import pformat

from twisted.internet.task import LoopingCall


__all__ = ['DiagnosticsOutputFormat', 'DiagnosticsProvider', 'DiagnosticsService']

logger = logging.getLogger(__name__)


class DiagnosticsOutputFormat(object):
    string = 0
    json = 1
    data = 2


class DiagnosticsProvider(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def get_diagnostics(self, output_format):
        pass

    @staticmethod
    def _format_diagnostics(data, output_format):
        if output_format == DiagnosticsOutputFormat.string:
            if isinstance(data, basestring):
                return data
            return pformat(data)
        elif output_format == DiagnosticsOutputFormat.json:
            return json.dumps(data)
        elif output_format == DiagnosticsOutputFormat.data:
            return data
        raise ValueError("Unknown output format")


class DiagnosticsService(object):
    def __init__(self, output_format=None):
        self._providers = dict()
        self._output_format = output_format or DiagnosticsOutputFormat.string
        self._looping_call = None

    def register(self, provider, method=None, output_format=None):
        if isinstance(provider, DiagnosticsProvider):
            if output_format is None:
                output_format = self._output_format
            self._providers[hash(provider)] = dict(
                provider=provider,
                cls=provider.__class__,
                cls_name=provider.__class__.__name__,
                method=method,
                output_format=output_format
            )

    def unregister(self, provider):
        if provider:
            self._providers.pop(hash(provider), None)

    def unregister_all(self):
        self._providers = {}

    def start_looping_call(self, interval=300):
        if not self._looping_call:
            self._looping_call = LoopingCall(self.log_diagnostics)
            self._looping_call.start(interval)

    def stop_looping_call(self):
        if self._looping_call:
            self._looping_call.stop()

    def log_diagnostics(self):
        for v in self._providers.itervalues():
            method = v['method']
            data = v['provider'].get_diagnostics(v["output_format"])

            if method:
                method(data)
            else:
                cls_name = v['cls_name']
                logger.debug("Diagnostics: {}\n{}\n".format(
                    cls_name, data
                ))
