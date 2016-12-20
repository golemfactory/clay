from golem.interface.command import group, CommandHelper, Argument, command, CommandResult


@group(name="envs", help="Manage environments")
class Environments(object):

    name = Argument('name', help="Environment name")

    table_headers = ['name', 'supported', 'active', 'performance', 'description']

    sort = Argument(
        '--sort',
        choices=table_headers,
        optional=True,
        default=None,
        help="Sort environments"
    )

    @command(argument=sort, help="Show environments")
    def show(self, sort):

        deferred = Environments.client.get_environments_perf()
        result = CommandHelper.wait_for(deferred) or []

        values = []

        for env in result:
            values.append([
                env['id'],
                str(env['supported']),
                str(env['active']),
                str(env['performance']),
                env['description']
            ])

        return CommandResult.to_tabular(Environments.table_headers, values, sort=sort)

    @command(argument=name, help="Enable environment")
    def enable(self, name):
        deferred = Environments.client.enable_environment(name)
        return CommandHelper.wait_for(deferred)

    @command(argument=name, help="Disable environment")
    def disable(self, name):
        deferred = Environments.client.disable_environment(name)
        return CommandHelper.wait_for(deferred)

    @command(argument=name, help="Recount performance for an environment")
    def recount(self, name):
        deferred = Environments.client.run_benchmark(name)
        return CommandHelper.wait_for(deferred, timeout=1800)
