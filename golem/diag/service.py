import abc

import json
import logging
from pprint import pformat

from golem.core.service import LoopingCallService


__all__ = ['DiagnosticsOutputFormat', 'DiagnosticsProvider', 'DiagnosticsService']

logger = logging.getLogger(__name__)


class DiagnosticsOutputFormat(object):
    string = 0
    json = 1
    data = 2


class DiagnosticsProvider(object, metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def get_diagnostics(self, output_format):
        pass

    @staticmethod
    def _format_diagnostics(data, output_format):
        if output_format == DiagnosticsOutputFormat.string:
            if isinstance(data, str):
                return data
            return pformat(data)
        elif output_format == DiagnosticsOutputFormat.json:
            return json.dumps(data)
        elif output_format == DiagnosticsOutputFormat.data:
            return data
        raise ValueError("Unknown output format")


class DiagnosticsService(LoopingCallService):
    def __init__(self, output_format=None):
        super().__init__(interval_seconds=300)
        self._providers = dict()
        self._output_format = output_format or DiagnosticsOutputFormat.string

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

    def _run(self):
        for v in list(self._providers.values()):
            method = v['method']
            data = v['provider'].get_diagnostics(v["output_format"])

            if method:
                method(data)
            else:
                cls_name = v['cls_name']
                logger.debug("Diagnostics: {}\n{}\n".format(
                    cls_name, data
                ))
