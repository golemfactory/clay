from scripts.concent_integration_tests.tests.playbooks.base import (
    NodeTestPlaybook
)


class TaskTimeout(NodeTestPlaybook):
    provider_node_script = 'provider/no_second_wtct'
    requestor_node_script = 'requestor/debug'
    task_settings = '2_short'

