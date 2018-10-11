from golem.core.deferred import sync_wait
from golem.interface.command import doc, group, command, CommandResult, Argument
from golem.resource.dirmanager import DirectoryType


@group(name="res", help="Manage resources")
class Resources(object):

    client = None

    provider = Argument(
        "--provider",
        optional=True,
        help="For provider role"
    )

    requestor = Argument(
        "--requestor",
        optional=True,
        help="For requestor role"
    )

    @doc("Show information on used resources")
    def show(self):
        res = sync_wait(Resources.client.get_res_dirs_sizes(), timeout=None)
        return CommandResult.to_tabular(list(res.keys()), [list(res.values())])

    @command(arguments=(provider, requestor),
             help="Clear provider / requestor resources")
    def clear(self, provider, requestor):

        if not provider and not requestor:
            return CommandResult(error="Target role was not specified "
                                       "(provider / requestor)")

        clear = Resources.client.clear_dir

        if requestor:
            return sync_wait(clear(DirectoryType.RECEIVED), timeout=None)
        elif provider:
            return sync_wait(clear(DirectoryType.DISTRIBUTED), timeout=None)
