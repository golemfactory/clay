#!/usr/bin/env python
import time

from scripts.concent_node_tests import helpers

provider_node = helpers.run_golem_node('provider/regular')
requestor_node = helpers.run_golem_node('requestor/regular')

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
