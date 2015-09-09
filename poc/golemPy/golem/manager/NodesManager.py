import sys

from PyQt4.QtGui import QApplication, QDialog
from PyQt4.QtCore import QTimer
from threading import Lock

from golem.ui.manager import NodesManagerWidget
from golem.ui.uicustomizer import ManagerUiCustomizer, NodeDataState
from NodeStateSnapshot import NodeStateSnapshot
from networksimulator import GLOBAL_SHUTDOWN, LocalNetworkSimulator
from NodesManagerLogic import NodesManagerLogicTest, EmptyManagerLogic
from server.NodesManagerServer import NodesManagerServer

#FIXME: potencjalnie mozna tez spiac ze soba managery i wtedy kontrolowac zdalnie wszystkie koncowki i sobie odpalac nody w miare potrzeb, ale to nie na najblizsza prezentacje zabawa
class NodesManager:

    ########################
    def __init__(self, manager_logic = None, port = 20301):
        self.app = QApplication(sys.argv)
        self.mainWindow = NodesManagerWidget(None)
        self.uic = ManagerUiCustomizer(self.mainWindow, self)
        self.timer = QTimer()
        self.timer.timeout.connect(self.polled_update)
        self.lock = Lock()
        self.statesBuffer = []
        self.manager_logic = manager_logic

        self.uic.enableDetailedView(False)

        self.manager_server = NodesManagerServer(self, port)

         #FIXME: some shitty python magic
    def closeEvent_(self, event):
        try:
            self.manager_logic.get_reactor().stop()
            self.manager_logic.terminate_all_nodes()
        except Exception as ex:
            pass
        finally:
            GLOBAL_SHUTDOWN[ 0 ] = True
            event.accept()

        setattr(self.mainWindow.window.__class__, 'closeEvent', closeEvent_)

     ########################
    def set_manager_logic(self, manager_logic):
        self.manager_logic = manager_logic

    ########################
    def cur_selected_node(self):
        return None

    ########################
    def append_state_update(self, update):
        with self.lock:
            self.statesBuffer.append(update)

    ########################
    def polled_update(self):
        with self.lock:
            for ns in self.statesBuffer:
                self.update_node_state(ns)

            self.statesBuffer = []

    ########################
    def execute(self, using_qt4_reactor = False):
        self.mainWindow.show()
        self.timer.start(100)
        if not using_qt4_reactor:
            sys.exit(self.app.exec_())

    ########################
    def update_node_state(self, ns):
        assert isinstance(ns, NodeStateSnapshot)

        tcss = ns.get_task_chunk_state_snapshot()

        ndslt = {}
        for sp in tcss.values():
            ndslt[ sp.get_chunk_id() ] = {    "chunkProgress" : sp.get_progress(),
                                            "cpu_power" : "{}".format(sp.get_cpu_power()),
                                            "timeLeft" : "{}".format(sp.get_estimated_time_left()),
                                            "cshd" : sp.get_chunk_short_descr()
                                        }

        ndscs = {}

        ltss = ns.get_local_task_state_snapshot()
        for sp in ltss.values():
            ndscs[ sp.get_task_id() ] = {   "taskProgress" : sp.get_progress(),
                                            "alloc_tasks" : "{}".format(sp.get_total_tasks()),
                                            "alloc_chunks" : "{}".format(sp.get_total_chunks()),
                                            "active_tasks" : "{}".format(sp.get_active_tasks()),
                                            "active_chunks" : "{}".format(sp.get_active_chunks()),
                                            "chunks_left" : "{}".format(sp.get_chunks_left()),
                                            "ltshd" : sp.get_task_short_desc()
                                       }

        ep = "{}:{}".format(ns.endpoint_addr, ns.endpoint_port)
        ts = ns.get_formatted_timestamp()
        pn = "{}".format(ns.get_peers_num())
        tn = "{}".format(ns.get_tasks_num())
        lm = ""
        if len(ns.get_last_network_messages()) > 0:
            lm = ns.get_last_network_messages()[-1][ 0 ] + str(ns.get_last_network_messages()[-1][ 4 ])


        ir = ns.is_running()

        node_data_state = NodeDataState(ir, ns.uid, ts, ep, pn, tn, lm, ndscs, ndslt)

        self.uic.UpdateNodePresentationState(node_data_state)

    ########################
    def run_additional_nodes(self, num_nodes):
        self.manager_logic.run_additional_nodes(num_nodes)

    ########################
    def run_additional_local_nodes(self, uid, num_nodes):
        self.manager_logic.run_additional_local_nodes(uid, num_nodes)

    ########################
    def terminate_node(self, uid):
        self.manager_logic.terminate_node(uid)

    ########################
    def terminate_all_nodes(self):
        self.manager_logic.terminate_all_nodes()

    ########################
    def terminate_all_local_nodes(self, uid):
        self.manager_logic.terminate_all_local_nodes(uid)

    ########################
    def load_task(self, uid, file_path):
        self.manager_logic.load_task(uid, file_path)

    ########################
    def enqueue_new_task(self, uid, w, h, num_samples_per_pixel, file_name):
        self.manager_logic.enqueue_new_task(uid, w, h, num_samples_per_pixel, file_name)

if __name__ == "__main__":

    manager = NodesManager()

    num_nodes = 1
    max_local_tasks = 2
    max_remote_tasks = 30
    max_loc_task_duration = 10.0
    max_rem_task_duration = 28.0
    max_inner_update_delay = 2.0
    node_spawn_delay = 1.0

    simulator = LocalNetworkSimulator(manager, num_nodes, max_local_tasks, max_remote_tasks, max_loc_task_duration, max_rem_task_duration, max_inner_update_delay, node_spawn_delay)
    manager.set_manager_logic(NodesManagerLogicTest(simulator))
    simulator.start()

    manager.execute()
