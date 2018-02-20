#!/usr/bin/env python

from golem_messages import cryptography
from golem_messages import message

from golem.core import common
from golem.network.concent import client

from tests.factories import messages as msg_factories


def main_send():
    print('#' * 80)
    keys = cryptography.ECCx(None)
    task_to_compute = message.TaskToCompute()
    task_to_compute.compute_task_def = message.ComputeTaskDef({
        'task_id': 'a1',
        'subtask_id': 'a1/1',
        'deadline': common.timeout_to_deadline(10),
    })
    msg = msg_factories.ForceReportComputedTask()
    print('Prepared message:', msg)
    print('Sending to concent...')
    content = client.send_to_concent(msg, keys.raw_privkey, keys.raw_pubkey)
    print('-' * 80)
    print(content)


def main_receive():
    print('#' * 80)
    keys = cryptography.ECCx(None)
    print('Receiving from concent...')
    content = client.receive_from_concent(keys.raw_pubkey)
    print('-' * 80)
    print(content)


if __name__ == '__main__':
    common.config_logging(suffix='_concent')
    main_receive()
    main_send()
