from scripts.node_integration_tests.playbooks.base import NodeTestPlaybook


class Playbook(NodeTestPlaybook):
    RPC_TASK_CREATE = 'comp.task_api.create'
