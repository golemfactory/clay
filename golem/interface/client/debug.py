from golem.core.deferred import sync_wait
from golem.interface.command import group, command, CommandResult, Argument
from golem.interface.exceptions import CommandException
from golem.rpc.mapping.rpcmethodnames import CORE_METHOD_MAP


def _build_alias_to_method():
    alias_to_method = dict()
    for method, alias in CORE_METHOD_MAP.items():
        alias_to_method[alias] = method
    return alias_to_method


@group(help="Debug RPC")
class Debug(object):
    client = None
    alias_to_method = _build_alias_to_method()

    vargs = Argument('vargs', vargs=True, help='RPC call parameters')

    @command(arguments=(vargs,), help="Debug RPC calls")
    def rpc(self, vargs):
        alias = vargs[0]
        if alias not in Debug.alias_to_method:
            raise CommandException('Unknown alias: {}'.format(alias))

        method = getattr(Debug.client, Debug.alias_to_method[alias])
        deferred = method(*vargs[1:])
        status = sync_wait(deferred) or None

        return CommandResult(status)
