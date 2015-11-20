from threading import Thread, Lock
import time
import random
import logging

from PyQt4 import QtCore

from nodestatesnapshot import NodeStateSnapshot, LocalTaskStateSnapshot, TaskChunkStateSnapshot

logger = logging.getLogger(__name__)

GLOBAL_SHUTDOWN = [ False ]

class NodeSimulator(QtCore.QThread):

    #updateRequest = QtCore.pyqtSignal()

    ########################
    def __init__(self, simulator, id, uid, num_local_tasks, num_remote_tasks, local_task_duration, remote_task_duration, inner_update_delay):
        super(NodeSimulator, self).__init__()
            
        self.simulator = simulator
        self.id = id
        self.uid = uid
        self.num_local_tasks = num_local_tasks
        self.num_remote_tasks = num_remote_tasks
        self.local_task_duration = local_task_duration
        self.remote_task_duration = remote_task_duration
        self.start_time = time.time()
        self.inner_update_delay = inner_update_delay
        
        self.loc_progress = 0.0
        self.rem_progress = 0.0

        self.forced_quit = False

        self.local_addr = "127.0.0.1"
        self.local_port = int(random.random() * 60000.0 + 1024.0)
        self.peers_num = 0
        self.tasks_num = 0
        self.running = True
        
        self.addedTasks = []

        for i in range(num_local_tasks):
            self.addedTasks.append("Uninteresting taks desc {}".format(i))

    ########################
    def terminate(self):
        self.forced_quit = True

    ########################
    def enqueue_task(self, w, h, num_samples_per_pixel, file_name):
        self.num_local_tasks += 1
        self.totalDuration += self.local_task_duration
        extra_data = "w: {}, h: {}, spp: {}, file: {}".format(w, h, num_samples_per_pixel, file_name)

        self.addedTasks.append(extra_data)

    ########################
    def get_id(self):
        return self.id

    ########################
    def get_uid(self):
        return self.uid

    ########################
    def get_state_snapshot(self):
        add_peers = 1 if random.random() >= 0.45 else -1

        self.peers_num += add_peers

        if self.peers_num < 0:
            self.peers_num = 0
        if self.peers_num > 10:
            self.peers_num = 10

        add_tasks = 1 if random.random() >= 0.5 else -1

        self.tasks_num += add_tasks

        if self.tasks_num < 0:
            self.tasks_num = 0
        if self.tasks_num > 200:
            self.tasks_num = 200

        cur_time = time.time()

        ctl = self.remote_task_duration - (cur_time - self.rem_task_start_time)
        ctl = max(0.0, ctl)
        tcss = TaskChunkStateSnapshot('0xbaadf00d', 1600.0, ctl, self.rem_progress, "chunk data: {}".format(self.rem_task))

        all_chunks = 1000 * 1000

        total_tasks = int(1000.0 * self.loc_progress)
        total_chunks = 1000 * total_tasks
        
        active_random = random.random()
        active_tasks = int(active_random * total_tasks)
        active_chunks = int(active_random * total_chunks)

        descr = "nothing here"
        lc_t = self.loc_task

        if lc_t < len(self.addedTasks):
            descr = self.addedTasks[ lc_t ]

        ltss = LocalTaskStateSnapshot('0xcdcdcdcd', total_tasks, total_chunks, active_tasks, active_chunks, all_chunks - total_chunks, self.loc_progress, descr)

        return NodeStateSnapshot(self.running, self.uid, self.peers_num, self.tasks_num, self.local_addr, self.local_port, ['test message {}'.format(random.randint(0,200))], ['test message {}'.format(random.randint(10, 70))], { '0' : tcss }, { '0xcdcdcd' : ltss })

    ########################
    def run(self):

        start_time = time.time()
        self.loc_task_duration = self.num_local_tasks * self.local_task_duration
        self.rem_tasksDuration = self.num_remote_tasks * self.remote_task_duration

        self.totalDuration = max(self.loc_task_duration, self.rem_tasksDuration)

        self.loc_task = 0
        self.loc_task_start_time = start_time
        self.rem_task = 0
        self.rem_task_start_time = start_time

        logger_msg = "Starting node '{}' local tasks: {} remote tasks: {}".format(self.uid, self.num_local_tasks, self.num_remote_tasks)
        logger.info("{} ->local task dura: {} secs, remote task dura: {} secs".format(logger_msg, self.local_task_duration, self.remote_task_duration))

        while time.time() - start_time < self.totalDuration:
                
            if GLOBAL_SHUTDOWN[ 0 ]:
                logger.warning("{}: Global shutdown triggered - bailing out".format(self.uid))
                break

            if self.forced_quit:
                logger.warning("{}: Forced quit triggered - bailing out".format(self.uid))
                break

            time.sleep(self.inner_update_delay)

            cur_time = time.time()

            if self.loc_task < self.num_local_tasks:
                dt = cur_time - self.loc_task_start_time

                if dt <= self.local_task_duration:
                    self.loc_progress = dt / self.local_task_duration
                else:
                    self.loc_task_start_time = cur_time
                    self.loc_task += 1
                    self.loc_progress = 0.0

            if self.rem_task < self.num_remote_tasks:
                dt = cur_time - self.rem_task_start_time

                if dt <= self.remote_task_duration:
                    self.rem_progress = dt / self.remote_task_duration
                else:
                    self.rem_task_start_time = cur_time
                    self.rem_task += 1
                    self.rem_progress = 0.0

            self.simulator.update_requested(self.id)
            #self.updateRequest.emit()
            #self.emit(QtCore.SIGNAL("Activated()"),self.dupa, QtCore.Qt.QueuedConnection)
            #print "\r                                                                      ",
            #print "\r{:3} : {}   {:3} : {}".format(loc_task, self.loc_progress, rem_task, self.rem_progress),

        logger.info("Finished node '{}'".format(self.uid))
        
        if self.running:
            self.running = False
            self.simulator.update_requested(self.id)

class LocalNetworkSimulator(Thread):

    ########################
    def __init__(self, manager, num_nodes, max_local_tasks, max_remote_tasks, max_local_task_duration, max_remote_task_duration, max_inner_update_delay, node_spawn_delay):
        super(LocalNetworkSimulator, self).__init__()

        self.manager = manager
        self.num_nodes = num_nodes
        self.max_loc_tasks = max_local_tasks
        self.max_rem_tasks = max_remote_tasks
        self.max_loc_task_dura = max_local_task_duration
        self.max_rem_task_dura = max_remote_task_duration
        self.max_inner_update_delay = max_inner_update_delay
        self.node_spawn_delay = node_spawn_delay
        self.cur_node = 0
        self.lock = Lock()

        self.nodes = []

    ########################
    def terminate_all_nodes(self):
        with self.lock:
            for node in self.nodes:
                node.terminate()

    ########################
    def terminate_node(self, uid):
        with self.lock:
            for i, node in enumerate(self.nodes):
                if node.get_uid() == uid:
                    node.terminate()
                    #self.nodes.pop(i)
                    break

    ########################
    def enqueue_node_task(self, uid, w, h, num_samples_per_pixel, file_name):
        with self.lock:
            for node in self.nodes:
                if node.get_uid() == uid:
                    node.enqueue_task(w, h, num_samples_per_pixel, file_name)

    ########################
    def add_new_node(self):
        with self.lock:
            node = self.create_new_node(self.cur_node)
            self.nodes.append(node)
            node.start()
            self.cur_node += 1
            #node.updateRequest.connect(self.update_requested)

    ########################
    def update_requested(self, id):
        self.manager.append_state_update(self.nodes[ id ].get_state_snapshot())

    ########################
    def get_randomized_up(self, value, scl = 1.4):
        return (0.1 +  scl * random.random()) * value

    ########################
    def get_randomized_down(self, value, scl = 0.7):
        return (1.0 - random.random() * scl) * value

    ########################
    def create_new_node(self, id):
        uid = "gen - uid - {}".format(id)
        num_loc_tasks = int(self.get_randomized_down(self.max_loc_tasks))
        num_rem_tasks = int(self.get_randomized_down(self.max_rem_tasks))
        loc_task_dura = self.get_randomized_down(self.max_loc_task_dura)
        rem_task_dura = self.get_randomized_down(self.max_rem_task_dura)
        update_delay = self.get_randomized_down(self.max_inner_update_delay)

        return NodeSimulator(self, id, uid, num_loc_tasks, num_rem_tasks, loc_task_dura, rem_task_dura, update_delay)

    ########################
    def run(self):
        time.sleep(1) #just out of decency

        cur_time = time.time()

        logger.info("Starting node simulator for {} nodes".format(self.num_nodes))

        while not GLOBAL_SHUTDOWN[ 0 ]:

            if self.cur_node < self.num_nodes:
                self.add_new_node()

            time.sleep(self.get_randomized_up(self.node_spawn_delay))

        logger.info("Local network simulator finished running.")
        logger.info("Waiting for nodes to finish")

        #10 seconds should be just enough for each node to do its cleanup
        for node in self.nodes:
            node.wait()

        logger.info("Simulation finished")
