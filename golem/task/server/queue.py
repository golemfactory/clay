import collections
import logging
import typing

from golem.network import nodeskeeper
from golem.network.transport import msg_queue

if typing.TYPE_CHECKING:
    from golem_messages import message

    from golem.task import taskkeeper
    from golem.task.tasksession import TaskSession


logger = logging.getLogger(__name__)

class TaskMessagesQueueMixin:
    """Message Queue functionality for TaskServer"""

    task_keeper: 'taskkeeper.TaskHeaderKeeper'

    def __init__(self):
        for attr_name in (
            'conn_established_for_type',
            'conn_failure_for_type',
            'conn_final_failure_for_type',
        ):
            if not hasattr(self, attr_name):
                setattr(self, attr_name, {})

        self.conn_established_for_type.update({
            'msg_queue': self.msg_queue_connection_established,
        })
        self.conn_failure_for_type.update({
            'msg_queue': self.msg_queue_connection_failure,
        })
        self.conn_final_failure_for_type.update({
            'msg_queue': self.msg_queue_connection_final_failure,
        })

    def send_message(self, node_id: str, msg: 'message.base.Message'):
        logger.debug('send_message(%r, %r)', node_id, msg)
        msg_queue.put(node_id, msg)

        # Temporary code to immediately initiate session
        node = self.task_keeper.find_newest_node(node_id)
        if node is None:
            node = nodeskeeper.get(node_id)
            logger.debug("Found in memory %r", node)
        if node is None:
            logger.debug(
                "Don't have any info about node. Will try later. node_id=%r",
                node_id,
            )
            return
        self._add_pending_request(  # type: ignore
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
        self.new_session_prepare(  # type: ignore
            session=session,
            key_id=node_id,
            conn_id=conn_id,
        )
        session.send_hello()
        for msg in msg_queue.get(node_id):
            session.send(msg)

    def msg_queue_connection_failure(self, conn_id, *args, **kwargs):
        def cbk(session):
            self.msg_queue_connection_established(session, conn_id, *args, **kwargs)
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

    def msg_queue_connection_final_failure(self, conn_id, *_args, **_kwargs):
        self.remove_pending_conn(conn_id)
        self.remove_responses(conn_id)
