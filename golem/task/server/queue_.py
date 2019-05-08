import logging
import time
import typing

from golem_messages import message

from golem.core import common
from golem.network import nodeskeeper
from golem.network.transport import msg_queue
from golem.network.transport import tcpserver

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem.task import taskkeeper
    from golem.task.tasksession import TaskSession


logger = logging.getLogger(__name__)

class TaskMessagesQueueMixin:
    """Message Queue functionality for TaskServer"""

    task_keeper: 'taskkeeper.TaskHeaderKeeper'
    forwarded_session_requests: typing.Dict[str, dict]

    def __init__(self):
        # Possible values of .sessions:
        #   None - PendingConnection
        #   TaskSession - session established
        # Keys are always node_id a.k.a. key_id
        self.sessions: 'typing.Dict[str, typing.Optional[TaskSession]]' = {}

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

    def initiate_session(self, node_id: str) -> None:
        if node_id in self.sessions:
            session = self.sessions[node_id]
            if session is not None:
                session.read_msg_queue()
            return

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
        result = self._add_pending_request(  # type: ignore
            'msg_queue',
            node,
            prv_port=node.prv_port,
            pub_port=node.pub_port,
            args={
                'node_id': node_id,
            }
        )
        if result:
            self.sessions[node_id] = None

    def remove_session_by_node_id(self, node_id):
        try:
            session = self.sessions[node_id]
        except KeyError:
            return
        del self.sessions[node_id]
        if session is None:
            return
        self.remove_session(session)

    def remove_session(self, session):
        session.disconnect(
            message.base.Disconnect.REASON.NoMoreMessages,
        )
        self.remove_pending_conn(session.conn_id)

    def connect_to_nodes(self):
        for node_id in msg_queue.waiting():
            self.initiate_session(node_id)

    def sweep_sessions(self):
        for node_id in self.sessions:
            session = self.sessions[node_id]
            if session is None:
                continue
            if session.is_active:
                continue
            self.remove_session_by_node_id(node_id)

    def msg_queue_connection_established(
            self,
            session: 'TaskSession',
            conn_id,
            node_id,
    ):
        try:
            if self.sessions[node_id] is not None:
                # There is a session already established
                # with this node_id. All messages will be processed
                # in that other session.
                session.dropped()
                return
        except KeyError:
            pass
        session.key_id = node_id
        session.conn_id = conn_id
        self.sessions[node_id] = session
        self._mark_connected(  # type: ignore
            conn_id,
            session.address,
            session.port,
        )
        self.forwarded_session_requests.pop(node_id, None)
        session.send_hello()

    def msg_queue_connection_failure(self, conn_id, *_args, **_kwargs):
        try:
            pc = self.pending_connections[conn_id]
        except KeyError:
            pass
        else:
            pc.status = tcpserver.PenConnStatus.WaitingAlt
            pc.time = time.time()

    def msg_queue_connection_final_failure(
            self,
            conn_id,
            node_id,
            *_args,
            **_kwargs,
    ):
        logger.debug(
            "Final connection failure for TaskSession."
            " conn_id=%s, node_id=%s",
            conn_id,
            common.short_node_id(node_id),
        )
        self.remove_pending_conn(conn_id)
        try:
            if self.sessions[node_id] is None:
                del self.sessions[node_id]
        except KeyError:
            pass
