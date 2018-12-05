from golem.core.deferred import sync_wait
from golem.interface.command import group, command, CommandResult, Argument


@group(help="Debug RPC")
class Debug(object):
    client = None

    vargs = Argument('vargs', vargs=True, help='RPC call parameters')

    @command(arguments=(vargs,), help="Debug RPC calls")
    def rpc(self, vargs):
        vargs = list(vargs)
        alias = vargs.pop(0)
        status = sync_wait(self.client._call(alias, *vargs)) # noqa pylint: disable=protected-access
        return CommandResult(status)

    @command(help="Dump uri to procedure mapping")
    def exposed_procedures(self):
        result = sync_wait(self.client._call('sys.exposed_procedures'))  # noqa pylint: disable=protected-access
        return result
