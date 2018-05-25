from golem.core.deferred import sync_wait
from golem.interface.command import command


@command(help="Show provider status", root=True)
def provider_status():
    return sync_wait(provider_status.client.get_provider_status())
