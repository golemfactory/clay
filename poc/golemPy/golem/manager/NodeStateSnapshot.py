from PyQt4 import QtCore

class TaskChunkStateSnapshot:
    
    def __init__(self, chunk_id, cpu_power, est_time_left, progress, chunk_short_desc):
        self.chunk_id = chunk_id
        self.cpu_power = cpu_power
        self.est_time_left = est_time_left
        self.progress = progress
        self.chunk_short_desc = chunk_short_desc

    def getChunkId(self):
        return self.chunk_id
    
    def getCpuPower(self):
        return self.cpu_power

    def getEstimatedTimeLeft(self):
        return self.est_time_left

    def get_progress(self):
        return self.progress

    def getChunkShortDescr(self):
        return self.chunk_short_desc

class LocalTaskStateSnapshot:

    def __init__(self, task_id, totalTasks, totalChunks, activeTasks, activeChunks, chunksLeft, progress, taskShortDescr):
        self.task_id = task_id
        self.totalTasks = totalTasks 
        self.totalChunks = totalChunks
        self.activeTasks = activeTasks
        self.activeChunks = activeChunks
        self.chunksLeft = chunksLeft
        self.progress = progress
        self.taskShortDescr = taskShortDescr

    def get_task_id(self):
        return self.task_id

    def get_total_tasks(self):
        return self.totalTasks
    
    def get_total_chunks(self):
        return self.totalChunks

    def get_active_tasks(self):
        return self.activeTasks

    def get_active_chunks(self):
        return self.activeChunks

    def get_chunks_left(self):
        return self.chunksLeft

    def get_progress(self):
        return self.progress

    def get_task_short_desc(self):
        return self.taskShortDescr

#FIXME: REGISTER number of local and remote tasks processed by current node (and number of successes and failures as well) - and show it in this manager
#FIXME: also add a boolean flag indicating whether there is any active local/rempote task being calculated
class NodeStateSnapshot:

    def __init__(self, running = True, uid = 0, peers_num = 0, tasks_num = 0, endpointAddr = "", endpointPort = "", last_network_messages = [], last_task_messages = [], tcss = {}, ltss = {}):
        self.uid                    = uid
        self.timestamp              = QtCore.QTime.currentTime()
        self.endpointAddr           = endpointAddr
        self.endpointPort           = endpointPort
        self.peers_num               = peers_num
        self.tasks_num               = tasks_num
        self.last_network_messages    = last_network_messages
        self.last_task_messages       = last_task_messages
        self.taskChunkState         = tcss
        self.localTaskState         = ltss
        self.running                = running

    def is_running(self):
        return self.running

    def getUID(self):
        return self.uid

    def getFormattedTimestamp(self):
        return self.timestamp.toString("hh:mm:ss.zzz")

    def getEndpointAddr(self):
        return self.endpointAddr

    def getEndpointPort(self):
        return self.endpointPort

    def getPeersNum(self):
        return self.peers_num

    def get_tasks_num(self):
        return self.tasks_num

    def getLastNetworkMessages(self):
        return self.last_network_messages

    def get_last_task_messages(self):
        return self.last_task_messages

    def get_taskChunkStateSnapshot(self):
        return self.taskChunkState

    def get_local_task_state_snapshot(self):
        return self.localTaskState

    def __str__(self):
        return "Nothing here"
        #ret = str(self.getUID())+ " ----- \n" + "peers count: " + str(self.getPeersNum()) + "\n" + "tasks count: " + str(self.get_tasks_num()) + "\n"
        #ret += "remote progress: " + str(self.getRemoteProgress()) + "\n" + "lockal progress: " + str(self.getLocalProgress()) + "\n"
        #ret += "last net comunication: " + str(self.getLastNetworkMessages()) + "\n"
        #ret += "last task comunication: " + str(self.get_last_task_messages())
        #return ret

if __name__ == "__main__":

    ns = NodeStateSnapshot("some uiid", 0.2, 0.7)

    print ns.getUID()
    print ns.getFormattedTimestamp()
    print ns.getLocalProgress()
    print ns.getRemoteProgress()
