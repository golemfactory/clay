# pylint: disable=no-value-for-parameter
import asyncio
import datetime
import json
import logging
import time
from typing import Optional, Dict
from urllib.parse import urljoin

import requests
from pydispatch import dispatcher

from golem.core import golem_async
from golem.core import variables
from golem.decorators import log_error
from golem.task.taskproviderstats import ProviderStats
from golem.task.taskrequestorstats import CurrentStats, FinishedTasksStats, \
    AggregateTaskStats
from .model import statssnapshotmodel
from .model.loginlogoutmodel import LoginModel, LogoutModel
from .model.nodemetadatamodel import NodeInfoModel, NodeMetadataModel
from .model.taskcomputersnapshotmodel import TaskComputerSnapshotModel

log = logging.getLogger('golem.monitor')


@golem_async.throttle(datetime.timedelta(minutes=10))
def log_throttled(msg, d):
    log.warning(msg, d)


class SystemMonitor(object):
    def __init__(self,
                 meta_data: NodeMetadataModel,
                 monitor_config: dict) -> None:
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        self.config = monitor_config

    @golem_async.taskify()
    async def p2p_listener(self, *_, event='default', ports=None, **__):
        if event != 'listening':
            return
        await self.ping_request(ports)

    async def ping_request(self, ports) -> None:
        result = await self.ping_request_io(ports)
        if not result:
            return

        port_statuses = result.get('port_statuses')
        if port_statuses:
            for port_status in port_statuses:
                # This signal will be handled in this functions thread
                dispatcher.send(
                    signal='golem.p2p',
                    event='open' if port_status['is_open'] else 'unreachable',
                    port=port_status['port'],
                    description=port_status['description']
                )

        if result['time_diff'] > variables.MAX_TIME_DIFF:
            # This signal will be handled in this functions thread
            dispatcher.send(
                signal='golem.p2p',
                event='unsynchronized',
                time_diff=result['time_diff']
            )

    @golem_async.run_in_thread()
    def ping_request_io(self, ports, **_kwargs) -> Optional[Dict]:
        timeout = 2.5  # seconds

        for host in self.config['PING_ME_HOSTS']:
            try:
                response = requests.post(
                    urljoin(host, 'ping-me'),
                    data={
                        'ports': ports,
                        'timestamp': time.time()
                    },
                    timeout=timeout,
                )
                result = response.json()
                log.debug('Ping result: %r', result)
                return result
            except (requests.RequestException, ValueError):
                log.exception('Ping error (%r)', host)
        return None

    # pylint: disable=unused-argument
    @golem_async.taskify()
    @log_error()
    async def dispatch_listener(
            self,
            sender,
            signal,
            event='default',
            **kwargs,
    ):
        """ Main PubSub listener for golem_monitor channel """
        method_name = "on_%s" % (event,)
        if not hasattr(self, method_name):
            log.warning('Unrecognized event received: golem_monitor %s', event)
            return
        result = getattr(self, method_name)(**kwargs)
        if asyncio.iscoroutine(result):
            await result

    # Initialization

    def start(self):
        dispatcher.connect(
            self.dispatch_listener,
            signal='golem.monitor',
        )
        dispatcher.connect(
            self.p2p_listener,
            signal='golem.p2p',
        )

    @golem_async.run_in_thread()
    def send(self, model, loop):
        url = self.config['HOST']
        request_timeout = self.config['REQUEST_TIMEOUT']
        proto_ver = self.config['PROTO_VERSION']
        payload = json.dumps(
            {
                'proto_ver': proto_ver,
                'data': model.dict_repr(),
            },
            indent=4,
        )
        log.debug('sending payload=%s', payload)
        try:
            result = requests.post(
                url,
                data=payload,
                headers={'content-type': 'application/json'},
                timeout=request_timeout
            )
            log.debug("Result %r", result)
            if not result.status_code == 200:
                log.debug("Monitor request error. result=%r", result)
        except requests.exceptions.RequestException as e:
            asyncio.ensure_future(log_throttled(
                'Problem sending payload to: %(url)r, because %(e)s',
                {
                    'url': url,
                    'e': e,
                },
            ), loop=loop)

    # handlers

    async def on_shutdown(self):
        await self.on_logout()

    async def on_login(self):
        await self.send(LoginModel(self.meta_data))

    async def on_config_update(self, meta_data):
        self.meta_data = meta_data
        self.node_info = NodeInfoModel(meta_data.cliid, meta_data.sessid)
        await self.on_login()

    async def on_computation_time_spent(self, success, value):
        msg = statssnapshotmodel.ComputationTime(
            self.meta_data,
            success,
            value
        )
        await self.send(msg)

    async def on_logout(self):
        await self.send(LogoutModel(self.meta_data))

    async def on_stats_snapshot(self, known_tasks, supported_tasks, stats):
        msg = statssnapshotmodel.StatsSnapshotModel(
            self.meta_data,
            known_tasks,
            supported_tasks,
            stats
        )
        await self.send(msg)

    async def on_vm_snapshot(self, vm_data):
        msg = statssnapshotmodel.VMSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            vm_data
        )
        await self.send(msg)

    async def on_peer_snapshot(self, p2p_data):
        msg = statssnapshotmodel.P2PSnapshotModel(
            self.meta_data.cliid,
            self.meta_data.sessid,
            p2p_data
        )
        await self.send(msg)

    async def on_task_computer_snapshot(self, task_computer):
        msg = TaskComputerSnapshotModel(self.meta_data, task_computer)
        await self.send(msg)

    async def on_requestor_stats_snapshot(
            self,
            current_stats: CurrentStats,
            finished_stats: FinishedTasksStats,
    ):
        msg = statssnapshotmodel.RequestorStatsModel(
            self.meta_data, current_stats, finished_stats)
        await self.send(msg)

    async def on_requestor_aggregate_stats_snapshot(
            self,
            stats: AggregateTaskStats,
    ):
        msg = statssnapshotmodel.RequestorAggregateStatsModel(
            self.meta_data, stats)
        await self.send(msg)

    async def on_provider_stats_snapshot(self, stats: ProviderStats):
        msg = statssnapshotmodel.ProviderStatsModel(self.meta_data, stats)
        await self.send(msg)
