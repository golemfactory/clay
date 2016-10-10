from golem.interface.command import doc, group, command, CommandResult, Argument, CommandHelper


@group(name="res", help="Manage resources")
class Resources(object):

    client = None

    provider = Argument(
        "--provider",
        optional=True,
        help="For provider role"
    )

    requester = Argument(
        "--requester",
        optional=True,
        help="For requester role"
    )

    @doc("Show information on used resources")
    def show(self):
        return CommandHelper.wait_for(Resources.client.get_res_dirs_sizes(), timeout=120)

    @command(arguments=(provider, requester), help="Clear provider / requester resources")
    def clear(self, provider, requester):

        if not provider and not requester:
            return CommandResult(error="Target role was not specified (provider / requester)")

        if provider:
            CommandHelper.wait_for(Resources.client.remove_received_files())
            return CommandHelper.wait_for(Resources.client.remove_computed_files())

        elif requester:
            return CommandHelper.wait_for(Resources.client.remove_distributed_files())
