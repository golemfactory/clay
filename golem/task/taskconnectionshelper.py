import time

import weakref

from golem.core.ordereddict import SizedOrderedDict
from golem.network.p2p.p2pservice import FORWARD_BATCH_SIZE

REMOVE_OLD_INTERVAL = 180
FORWARD_QUEUE_LEN = FORWARD_BATCH_SIZE * 10


class TaskConnectionsHelper(object):
    """ Keeps information about task connections that should be set with a help of p2p network """

    def __init__(self):
        """ Create a new instance of task connection helper that keeps information about information
        that has been passed and processed by a node.
        """
        self.task_server = None
        # forwarded conn registry of timestamps
        self.conn_to_set = {}
        # forwarded conn queue (FIFO)
        self.conn_to_set_queue = SizedOrderedDict(FORWARD_QUEUE_LEN)
        self.last_remove_old = time.time()  # when was the last time when old connections were removed
        self.remove_old_interval = REMOVE_OLD_INTERVAL  # How often should be information about old connections cleared
        self.conn_to_start = {}  # information about connection requests with this node

    def is_new_conn_request(self, key_id, node_info):
        """ Check whether request for start connection with given conn_id has
        occurred before (in a latest remove_old_interval)
        :param key_id: public key of a node that is asked to start task session
        with node from node info
        :param Node node_info: node that asks for a task connection to be
        started with him
        :return bool: return False if connection with given id is known,
        True otherwise
        """
        id_tuple = key_id, node_info.key
        if id_tuple in self.conn_to_set:
            return False

        self.conn_to_set[id_tuple] = time.time()
        return True

    def want_to_start(self, conn_id, node_info, super_node_info):
        """ Process request to start task session from this node to a node from node_info. If it's a first request
        with given id pass information to task server, otherwise do nothing.
        :param conn_id: connection id
        :param Node node_info: node that requests task session with this node
        :param Node|None super_node_info: information about supernode that has passed this information
        """
        if conn_id in self.conn_to_start:
            return
        self.conn_to_start[conn_id] = (node_info, super_node_info, time.time())
        self.task_server.start_task_session(node_info, super_node_info, conn_id)

    def sync(self):
        """ Remove old entries about connections """
        cur_time = time.time()
        if cur_time - self.last_remove_old <= self.remove_old_interval:
            return
        self.last_remove_old = cur_time
        self.conn_to_set = dict([
            y_z for y_z in self.conn_to_set.items()
            if cur_time - y_z[1] < self.remove_old_interval
        ])
        self.conn_to_start = dict([
            y_z1 for y_z1 in self.conn_to_start.items()
            if cur_time - y_z1[1][2] < self.remove_old_interval
        ])

    def cannot_start_task_session(self, conn_id):
        """ Inform task server that cannot pass request with given conn id
        :param conn_id: id of a connection that can't be established
        """
        self.task_server.final_conn_failure(conn_id)

    def forward_queue_put(self, peer, key_id, node_info, conn_id,
                          super_node_info):
        """
        Append a forwarded request to the queue. Any existing request issued by
        this particular sender (node_info.key) will be removed.

        :param peer: peer session to send the message to
        :param key_id: key id of a node that should open a task session
        :param node_info: information about node that requested session
        :param conn_id: connection id for reference
        :param super_node_info: information about node with public ip that took
        part in message transport
        :return: None
        """

        sender = node_info.key
        args = key_id, node_info, conn_id, super_node_info
        self.conn_to_set_queue.pop(sender, None)
        self.conn_to_set_queue[sender] = weakref.ref(peer), args

    def forward_queue_get(self, count=5):
        """
        Get <count> forward requests from the queue.

        :param count: number of requests to retrieve
        :return: list of min(len(queue), count) queued requests
        """
        entries = []
        try:
            for _ in range(count):
                _, entry = self.conn_to_set_queue.popitem(last=False)
                entries.append(entry)
        except KeyError:
            pass
        return entries
