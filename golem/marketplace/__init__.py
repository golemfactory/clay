from rust.golem import marketplace__order_providers as order_providers  # noqa pylint: disable=no-name-in-module,import-error


class Offer:
    def __init__(self, scaled_price: float) -> None:
        self.scaled_price = scaled_price
        self.reputation = 0.0
        self.quality = (0.0, 0.0, 0.0, 0.0)
