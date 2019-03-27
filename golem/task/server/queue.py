import collections
import logging
import typing

from golem.network.transport import msg_queue

if typing.TYPE_CHECKING:
    from golem_messages import message

    from golem.task.tasksession import TaskSession


logger = logging.getLogger(__name__)

class TaskMessagesQueueMixin:
    """Message Queue functionality for TaskServer"""

    def __init__(self):
        self.conn_established_for_type.update({
            'msg_queue': self.msg_queue_connection_established,
        })
        self.conn_failure_for_type.update({
            'msg_queue': self.msg_queue_connection_failure,
        })
        self.conn_final_failure_for_type.update({
            'msg_queue': self.msg_queue_connection_final_failure,
        })

        # FIXME bandaid solution
        self.remembered_nodes = {}

    def send_message(self, node_id: str, msg: 'messages.base.Message'):
        # XXX Differentiate between node id and key id
        logger.debug('send_message(%r, %r)', node_id, msg)
        msg_queue.put(node_id, msg)
        # Temporary code to 
        node = self.task_keeper.find_newest_node(node_id)
        if node is None:
            node = self.remembered_nodes.get(node_id)
            logger.debug("Found in memory %r", node)
        if node is None:
            logger.debug("Don't have any info about node. node_id=%r", node_id)
            logger.debug("Known nodes: %r", list(self.remembered_nodes.keys()))
            wyjeb
            return
        self._add_pending_request(
            'msg_queue',
            node,
            prv_port=node.prv_port,
            pub_port=node.pub_port,
            args={
                'node_id': node_id,
            }
        )

    def msg_queue_connection_established(
        self,
        session: 'TaskSession',
        conn_id,
        node_id,
    ):
        self.new_session_prepare(
            session=session,
            key_id=node_id,
            conn_id=conn_id,
        )
        session.send_hello()
        for msg in msg_queue.get(node_id):
            session.send(msg)

    def msg_queue_connection_failure(self, conn_id, *args, **kwargs):
        def cbk(session):
            self.msg_queue_connection_established(session, *args, **kwargs)
        try:
            self.response_list[conn_id].append(cbk)
        except KeyError:
            self.response_list[conn_id] = collections.deque([cbk])
        try:
            pc = self.pending_connections[conn_id]
        except KeyError:
            pass
        else:
            pc.status = PenConnStatus.WaitingAlt
            pc.time = time.time()

    def msg_queue_connection_final_failure(self, *_args, **_kwargs):
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)
