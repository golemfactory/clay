#!/usr/bin/env python
from argparse import ArgumentParser
import time

from scripts.node_integration_tests import helpers

parser = ArgumentParser(
    description="Run a pair of golem nodes with default test parameters"
)
parser.add_argument(
    '--provider-datadir',
    default=helpers.mkdatadir('provider'),
    help="the provider node's datadir",
)
parser.add_argument(
    '--requestor-datadir',
    default=helpers.mkdatadir('requestor'),
    help="the requestor node's datadir",
)
args = parser.parse_args()

provider_node = helpers.run_golem_node(
    'provider/debug', '--datadir', args.provider_datadir)
requestor_node = helpers.run_golem_node(
    'requestor/debug', '--datadir', args.requestor_datadir
)

provider_queue = helpers.get_output_queue(provider_node)
requestor_queue = helpers.get_output_queue(requestor_node)

try:
    while True:
        time.sleep(1)
        helpers.print_output(provider_queue, 'PROVIDER ')
        helpers.print_output(requestor_queue, 'REQUESTOR ')

        provider_exit = provider_node.poll()
        requestor_exit = requestor_node.poll()
        helpers.report_termination(provider_exit, "Provider")
        helpers.report_termination(requestor_exit, "Requestor")
        if provider_exit is not None and requestor_exit is not None:
            break

except KeyboardInterrupt:
    helpers.gracefully_shutdown(provider_node, 'Provider')
    helpers.gracefully_shutdown(requestor_node, 'Requestor')
