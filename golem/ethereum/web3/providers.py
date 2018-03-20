from typing import Optional

from web3.exceptions import CannotHandleRequest
from web3.providers import BaseProvider


class ProviderProxy(BaseProvider):

    def __init__(self, provider: Optional[BaseProvider] = None) -> None:
        self.provider = provider

    def make_request(self, method, params):
        if self.provider:
            return self.provider.make_request(method, params)
        raise CannotHandleRequest('No underlying provider is available')

    def isConnected(self):
        return self.provider and self.provider.isConnected()
