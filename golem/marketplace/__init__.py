# pylint: disable=unused-import
from typing import Type, Union

from bidict import bidict

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

DEFAULT_REQUESTOR_MARKET_STRATEGY = RequestorBrassMarketStrategy
DEFAULT_PROVIDER_MARKET_STRATEGY = ProviderBrassMarketStrategy

REQUESTOR_MARKET_STRATEGIES = bidict({
    'wasm': RequestorWasmMarketStrategy,
    'brass': RequestorBrassMarketStrategy,
})


# Using Union; type(Type[...]) check is failing in dataclasses-json
def requestor_market_strategy_decode(
        strategy: Union[None, str, Type[RequestorMarketStrategy]]
) -> Type[RequestorMarketStrategy]:
    if not strategy:
        return DEFAULT_REQUESTOR_MARKET_STRATEGY
    elif isinstance(strategy, str):
        return REQUESTOR_MARKET_STRATEGIES[strategy.lower()]
    return strategy


def requestor_market_strategy_encode(
        strategy: Type[RequestorMarketStrategy],
) -> str:
    return REQUESTOR_MARKET_STRATEGIES.inverse[strategy]
