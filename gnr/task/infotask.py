import random
import logging
import cPickle as pickle
from golem.manager.client.nodesmanagerclient import NodesManagerClient
from golem.environments.environment import Environment
from golem.task.taskbase import ComputeTaskDef, result_types
from gnrtask import GNRTask, GNRTaskBuilder

logger = logging.getLogger(__name__)


class InfoTaskDefinition:
    def __init__(self):
        self.task_id = ""

        self.full_task_timeout = 0
        self.subtask_timeout = 0

        self.src_file = ""
        self.total_subtasks = 0

        self.manager_address = ""
        self.manager_port = 0


class InfoTaskBuilder(GNRTaskBuilder):
    def build(self):
        with open(self.task_definition.src_file) as f:
            src_code = f.read()
        return InfoTask(src_code,
                        self.node_name,
                        self.task_definition.task_id,
                        "",
                        0,
                        "",
                        Environment.get_id(),
                        self.task_definition.full_task_timeout,
                        self.task_definition.subtask_timeout,
                        0,
                        0,
                        self.task_definition.manager_address,
                        self.task_definition.manager_port,
                        self.task_definition.total_subtasks
                        )


class InfoTask(GNRTask):
    def __init__(self,
                 src_code,
                 node_name,
                 task_id,
                 owner_address,
                 owner_port,
                 owner_key_id,
                 environment,
                 ttl,
                 subtask_ttl,
                 resource_size,
                 estimated_memory,
                 max_price,
                 nodes_manager_address,
                 nodes_manager_port,
                 iterations):

        GNRTask.__init__(self, src_code, node_name, task_id, owner_address, owner_port, owner_key_id, environment,
                         ttl, subtask_ttl, resource_size, estimated_memory, max_price)

        self.num_subtasks = iterations

        self.nodes_manager_client = NodesManagerClient(nodes_manager_address, int(nodes_manager_port))
        self.nodes_manager_client.start()

    def abort(self):
        self.nodes_manager_client.dropConnection()

    def query_extra_data(self, perf_index, num_cores, node_id=None, node_name=None):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        hash = "{}".format(random.getrandbits(128))
        ctd.subtask_id = hash
        ctd.extra_data = {
            "start_task": self.last_task,
            "end_task": self.last_task + 1,
            "start_part": self.last_task,
            "end_part": self.last_task + 1}
        ctd.return_address = self.header.task_owner_address
        ctd.return_port = self.header.task_owner_port
        ctd.task_owner = self.header.task_owner
        ctd.short_description = "Standard info Task"
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        if self.last_task + 1 <= self.total_tasks:
            self.last_task += 1

        return ctd

    def computation_finished(self, task_id, task_result, dir_manager=None, result_type=0):
        if result_type != result_types['data']:
            logger.error("Only data result format supported")
            return
        try:
            msgs = pickle.loads(task_result)
            for msg in msgs:
                self.nodes_manager_client.send_client_state_snapshot(msg)
        except Exception as ex:
            logger.error("Error while interpreting results: {}".format(str(ex)))

    def get_resources(self, task_id, resource_header, resource_type=0):
        return None
