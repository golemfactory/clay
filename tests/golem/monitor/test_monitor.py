import random
from unittest import TestCase

from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.monitor.model.nodemetadatamodel import NodeMetadataModel
from golem.monitor.monitor import SystemMonitor
from golem.monitorconfig import MonitorConfig


class TestSystemMonitor(TestCase):
    def test_monitor_messages(self):
        nmm = NodeMetadataModel("CLIID", "SESSID", "win32", "1.3", "Random description\n\t with additional data",
                                ClientConfigDescriptor())
        m = MonitorConfig
        m.MONITOR_HOST = "http://localhost/88881"
        monitor = SystemMonitor(nmm, m)
        monitor.start()
        monitor.on_login()

        monitor.on_payment({"addr": "some address", "value": 30139019301})
        monitor.on_income("different address", 319031904194810)
        monitor.on_peer_snapshot([{"node_id": "firt node", "port": 19301},
                                  {"node_id": "second node", "port": 3193}])
        kt = int(10 * random.random())
        st = int(100 * random.random())
        ct = int(20 * random.random())
        twe = int(10 * random.random())
        twt = int(20 * random.random())
        monitor.on_stats_snapshot(kt, st, ct, twe, twt)
        comp_tasks = int(4 * random.random()) + 1
        tasks = ["task{}".format(i) for i in range(comp_tasks)]
        monitor.on_task_computer_snapshot('some_task_str', False, True, False, tasks)
        monitor.on_logout()
        monitor.shut_down()
