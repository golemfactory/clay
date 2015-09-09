import random
import logging
import cPickle as pickle

from golem.manager.client.NodesManagerClient import NodesManagerClient
from golem.environments.Environment import Environment
from golem.task.TaskBase import ComputeTaskDef, result_types
from GNRTask import GNRTask, GNRTaskBuilder

logger = logging.getLogger(__name__)

##############################################
class InfoTaskDefinition:
    def __init__(self):
        self.task_id = ""

        self.full_task_timeout    = 0
        self.subtask_timeout     = 0

        self.srcFile            = ""
        self.totalSubtasks      = 0

        self.manager_address     = ""
        self.manager_port        = 0

##############################################
class InfoTaskBuilder(GNRTaskBuilder):

    def build(self):
        with open(self.taskDefinition.srcFile) as f:
            src_code = f.read()
        return InfoTask(   src_code,
                            self.client_id,
                            self.taskDefinition.task_id,
                            "",
                            0,
                            "",
                            Environment.get_id(),
                            self.taskDefinition.full_task_timeout,
                            self.taskDefinition.subtask_timeout,
                            0,
                            0,
                            self.taskDefinition.manager_address,
                            self.taskDefinition.manager_port,
                            self.taskDefinition.totalSubtasks
                          )

##############################################
class InfoTask(GNRTask):

    def __init__(self,
                  src_code,
                  client_id,
                  task_id,
                  owner_address,
                  owner_port,
                  ownerKeyId,
                  environment,
                  ttl,
                  subtaskTtl,
                  resource_size,
                  estimated_memory,
                  nodesManagerAddress,
                  nodesManagerPort,
                  iterations):


        GNRTask.__init__(self, src_code, client_id, task_id, owner_address, owner_port, ownerKeyId, environment,
                            ttl, subtaskTtl, resource_size, estimated_memory)

        self.totalTasks = iterations

        self.nodes_manager_client = NodesManagerClient(nodesManagerAddress, int(nodesManagerPort))
        self.nodes_manager_client.start()

    #######################
    def abort (self):
        self.nodes_manager_client.dropConnection()

    #######################
    def query_extra_data(self, perf_index, num_cores, client_id = None):
        ctd = ComputeTaskDef()
        ctd.task_id = self.header.task_id
        hash = "{}".format(random.getrandbits(128))
        ctd.subtask_id = hash
        ctd.extra_data = {
                          "startTask" : self.lastTask,
                          "endTask": self.lastTask + 1 }
        ctd.return_address = self.header.task_owner_address
        ctd.return_port = self.header.task_owner_port
        ctd.task_owner = self.header.task_owner
        ctd.short_description = "Standard info Task"
        ctd.src_code = self.src_code
        ctd.performance = perf_index
        if self.lastTask + 1 <= self.totalTasks:
            self.lastTask += 1

        return ctd

    #######################
    def computation_finished(self, subtask_id, task_result, dir_manager = None, result_type = 0):
        if result_type != result_types['data']:
            logger.error("Only data result format supported")
            return
        try:
            msgs = pickle.loads(task_result)
            for msg in msgs:
                self.nodes_manager_client.sendClientStateSnapshot(msg)
        except Exception as ex:
            logger.error("Error while interpreting results: {}".format(str(ex)))

    #######################
    def prepare_resource_delta(self, task_id, resource_header):
        return None
