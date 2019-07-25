import asyncio
import functools
import logging
import threading
from asyncio import Event
from collections import defaultdict
from golem_messages.message import TaskToCompute
from pydispatch import dispatcher

logger = logging.getLogger(__name__)


class ConnectionEstablished(Event):
    def __init__(self, loop=None):
        super().__init__(loop=loop)
        self._task_session = None

    @property
    def task_session(self):
        return self._task_session

    @task_session.setter
    def task_session(self, task_session):
        self._task_session = task_session


class Communicator:
    computation_rejections_events = {}
    _event_loop = asyncio.new_event_loop()
    connection_established_events = defaultdict(
    functools.partial(ConnectionEstablished, loop=_event_loop))
    # def __init__(self):

    @classmethod
    def on_connect(cls, node_id, task_session):
        async def _on_connect():
            conn_established_event = \
                cls.connection_established_events.get(node_id)
            conn_established_event.task_session = task_session
            conn_established_event.set()
        logger.info('Node {} connected [task_session={}]'.format(node_id,
                                                                 task_session))
        asyncio.run_coroutine_threadsafe(_on_connect(), loop=cls._event_loop)

    @classmethod
    def on_disconnect(cls, node_id):
        async def _on_disconnect():
            conn_established_event = \
                cls.connection_established_events.get(node_id)
            conn_established_event.task_session = None
            conn_established_event.clear()
        asyncio.run_coroutine_threadsafe(_on_disconnect(),
                                         loop=cls._event_loop)

    @classmethod
    def on_computation_rejected(cls, provider_id, msg : TaskToCompute):
        async def _on_computation_rejected():
            event = cls.get_offer_rejected_event(provider_id, msg)
            event.set()
        asyncio.run_coroutine_threadsafe(_on_computation_rejected(),
                                         loop=cls._event_loop)

    @classmethod
    def get_offer_rejected_event(cls, provider_id, msg: TaskToCompute):
        x = cls.computation_rejections_events.get(provider_id, {})
        event = x.get(hash(msg), Event())
        x[hash(msg)] = event
        return event

    @classmethod
    def _send(cls, task_session, msg):
        task_session.send(msg)

    @classmethod
    def nominate_provider_with_assurance(cls, provider_id, task_id, timeout,
                                         on_failure, on_success, msg):

        async def _nominate():
            try:
                logger.info('Communicator::_nominate waiting for connection')
                conn_established_evt = \
                    cls.connection_established_events.get(provider_id)
                await asyncio.wait_for(conn_established_evt.wait(),
                                       loop=cls._event_loop, timeout=timeout)
                logger.info('Communicator::_nominate connected')
            except TimeoutError:
                logger.info('Cannot connect to provider {}. Timeout [] was '
                            'reached'.format(provider_id, timeout))
                cls._event_loop.run_in_executor(None, on_failure)
                return
            try:
                logger.info('Communicator::_nominate send [empty] task to provider')
                cls._send(conn_established_evt.task_session, msg)
                offer_rejected_evt = cls.get_offer_rejected_event(provider_id,
                                                                   msg)
                logger.info('Communicator:: waiting for acceptance by silence')

                await asyncio.wait_for(offer_rejected_evt.wait(),
                                       loop=cls._event_loop, timeout=timeout)
                offer_rejected_evt.clear()
                logger.info('Provider {} eventually resigned from computing '
                            'the task {}'.format(provider_id, task_id))
                cls._event_loop.run_in_executor(None, on_failure)
            except TimeoutError:
                logger.info('Provider {} decided to compute the task {}'.format(
                        provider_id, task_id))
                cls._event_loop.run_in_executor(None, on_success)
        logger.info('Communicator::nominate_provider_with_assurance')
        asyncio.run_coroutine_threadsafe(_nominate(), loop=cls._event_loop)


logger.info('Registering in dispatcher')
dispatcher.connect(Communicator.on_connect, signal='golem.peer.connected')
logger.info('Starting event loop')
threading.Thread(target=Communicator._event_loop.run_forever, daemon=True).start()
