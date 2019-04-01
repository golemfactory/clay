import typing

from golem.core.deferred import sync_wait
from golem.environments.minperformancemultiplier import MinPerformanceMultiplier
from golem.interface.command import group, Argument, command, CommandResult, \
    customize_output

if typing.TYPE_CHECKING:
    from golem.rpc.session import ClientProxy


# pylint: disable=no-self-use
@group(name="envs", help="Manage environments")
class Environments(object):
    client: 'ClientProxy'

    name = Argument('name', help="Environment name")
    multiplier = Argument('multiplier',
                          help='Multiplier; float value within range '
                               f'[{MinPerformanceMultiplier.MIN},'
                               f' {MinPerformanceMultiplier.MAX}]')

    table_headers = ['name', 'supported', 'active', 'performance',
                     'min accept. perf.', 'description']

    sort = Argument(
        '--sort',
        choices=table_headers,
        optional=True,
        default=None,
        help="Sort environments"
    )

    @command(argument=sort, help="Show environments")
    def show(self, sort):

        deferred = Environments.client.get_environments()
        result = sync_wait(deferred) or []

        values = []

        for env in result:
            values.append([
                env['id'],
                str(env['supported']),
                str(env['accepted']),
                str(env['performance']),
                str(env['min_accepted']),
                env['description']
            ])

        return CommandResult.to_tabular(Environments.table_headers, values,
                                        sort=sort)

    @command(argument=name, help="Enable environment")
    @customize_output('env {} enabled.', 'name', include_call_time=True)
    def enable(self, name):
        deferred = Environments.client.enable_environment(name)
        return sync_wait(deferred)

    @command(argument=name, help="Disable environment")
    @customize_output('env {} disabled.', 'name', include_call_time=True)
    def disable(self, name):
        deferred = Environments.client.disable_environment(name)
        return sync_wait(deferred)

    @command(argument=name, help="Recount performance for an environment")
    def recount(self, name):
        deferred = Environments.client.run_benchmark(name)
        return sync_wait(deferred, timeout=1800)

    @command(argument=multiplier, help="Sets accepted performance multiplier")
    @customize_output('envs perf_mult_set to {}', 'multiplier',
                      include_call_time=True)
    def perf_mult_set(self, multiplier):
        return sync_wait(
            Environments.client._call(
                'performance.multiplier.update',
                float(multiplier),
            ),
            timeout=3,
        )

    @command(help="Gets accepted performance multiplier")
    def perf_mult(self):
        result = sync_wait(
            Environments.client._call('performance.multiplier'),
            timeout=3,
        )
        return f'minimal performance multiplier is: {result}'
