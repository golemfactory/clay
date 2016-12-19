from golem.interface.command import doc, group, command, CommandResult, Argument, CommandHelper


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
            CommandHelper.wait_for(Resources.client.remove_received_files(),
                                   timeout=None)
            return CommandHelper.wait_for(Resources.client.remove_computed_files(),
                                          timeout=None)

        elif requestor:
            return CommandHelper.wait_for(Resources.client.remove_distributed_files(),
                                          timeout=None)
