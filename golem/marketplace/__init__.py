from typing import Tuple

from rust.golem import marketplace__order_providers as order_providers  # noqa pylint: disable=no-name-in-module,import-error


class Offer:
    def __init__(
            self,
            scaled_price: float,
            reputation: float,
            quality: Tuple[float, float, float, float]) -> None:
        self.scaled_price = scaled_price
        self.reputation = reputation
        self.quality = quality
