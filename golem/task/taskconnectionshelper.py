import time
import weakref

REMOVE_OLD_INTERVAL = 180


class TaskConnectionsHelper(object):
    """ Keeps information about task connections that should be set with a help of p2p network """

    def __init__(self):
        """ Create a new instance of task connection helper that keeps information about information
        that has been passed and processed by a node.
        """
        self.task_server = None
        self.conn_to_set = {}  # information about connection requests to other nodes
        self.last_remove_old = time.time()  # when was the last time when old connections were removed
        self.remove_old_interval = REMOVE_OLD_INTERVAL  # How often should be information about old connections cleared
        self.conn_to_start = {}  # information about connection requests with this node

    def is_new_conn_request(self, conn_id, key_id, node_info, super_node_info):
        """ Check whether request for start connection with given conn_id has occurred before
        (in a latest remove_old_interval)
        :param conn_id: connection id
        :param key_id: public key of a node that is asked to start task session with node from node info
        :param Node node_info: node that asks for a task connection to be started with him
        :param Node|None super_node_info: supernode that may help to mediate in a connection
        :return bool: return False if connection with given id is known, True otherwise
        """
        if conn_id in self.conn_to_set:
            return False
        else:
            self.conn_to_set[conn_id] = (key_id, weakref.ref(node_info), super_node_info, time.time())
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
        self.conn_to_set = dict(filter(lambda (y, z): cur_time - z[3] < self.remove_old_interval,
                                       self.conn_to_set.items()))
        self.conn_to_start = dict(filter(lambda(y, z): cur_time - z[2] < self.remove_old_interval,
                                         self.conn_to_start.items()))

    def cannot_start_task_session(self, conn_id):
        """ Inform task server that cannot pass request with given conn id
        :param conn_id: id of a connection that can't be established
        """
        self.task_server.final_conn_failure(conn_id)
