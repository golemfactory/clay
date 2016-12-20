from golem.interface.command import doc, group, command, CommandResult, Argument, CommandHelper
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
        return CommandHelper.wait_for(Resources.client.get_res_dirs_sizes(),
                                      timeout=None)

    @command(arguments=(provider, requestor), help="Clear provider / requestor resources")
    def clear(self, provider, requestor):

        if not provider and not requestor:
            return CommandResult(error="Target role was not specified (provider / requestor)")

        if provider:
            CommandHelper.wait_for(Resources.client.clear_dir(DirectoryType.RECEIVED), timeout=None)
            return CommandHelper.wait_for(Resources.client.clear_dir(DirectoryType.COMPUTED), timeout=None)

        elif requestor:
            return CommandHelper.wait_for(Resources.client.clear_dir(DirectoryType.DISTRIBUTED), timeout=None)
