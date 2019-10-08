# pylint: disable=unused-import
from enum import Enum

from .marketplace import (  # noqa
    RequestorMarketStrategy,
    ProviderMarketStrategy,
    ProviderPricing,
    ProviderPerformance,
    Offer
)
from .brass_marketplace import (  # noqa
    RequestorBrassMarketStrategy,
    ProviderBrassMarketStrategy
)
from .wasm_marketplace import (  # noqa
    RequestorWasmMarketStrategy,
    ProviderWasmMarketStrategy
)


class NameSerializableEnum(Enum):
    def serialize(self):
        return self.name

    @classmethod
    def deserialize(cls, name: str) -> 'NameSerializableEnum':
        try:
            return cls[name]
        except KeyError:
            return cls.default()

    @classmethod
    def default(cls):
        raise NotImplemented


class RequestorMarketStrategies(NameSerializableEnum):
    Brass = RequestorBrassMarketStrategy
    Wasm = RequestorWasmMarketStrategy

    @classmethod
    def default(cls) -> 'RequestorMarketStrategies':
        return cls.Brass


class ProviderMarketStrategies(NameSerializableEnum):
    Brass = ProviderBrassMarketStrategy
    Wasm = ProviderWasmMarketStrategy

    @classmethod
    def default(cls) -> 'ProviderMarketStrategies':
        return cls.Brass
