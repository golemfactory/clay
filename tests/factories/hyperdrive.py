from golem.appconfig import (
    DEFAULT_HYPERDRIVE_RPC_ADDRESS, DEFAULT_HYPERDRIVE_RPC_PORT
)


def hyperdrive_client_kwargs(wrapped=True):
    client_kwargs = {
        'host': DEFAULT_HYPERDRIVE_RPC_ADDRESS,
        'port': DEFAULT_HYPERDRIVE_RPC_PORT,
    }

    if not wrapped:
        return client_kwargs

    return {
        'client_kwargs': client_kwargs
    }
