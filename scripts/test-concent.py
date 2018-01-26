#!/usr/bin/env python

import hashlib

from golem_messages import cryptography
from golem_messages import message

from golem.core import common
from golem.network.concent import client


def main():
    keys = cryptography.ECCx(None)
    task_to_compute = message.TaskToCompute()
    task_to_compute.compute_task_def = message.ComputeTaskDef({
        'task_id': 'a1',
        'subtask_id': 'a1/1',
        'deadline': common.timeout_to_deadline(10),
    })
    msg = message.ForceReportComputedTask()
    msg.task_to_compute = task_to_compute
    msg.result_hash = 'sha1:{}'.format(
        hashlib.sha1(
            'Gruba warstwa próchnicy świadczy o długiej działalności'
            'organicznej. Panami rzeki są krokodyle i lwy, po lasach'
            'krążą bez obawy jaguary, pekari, tapiry i małpy. Jest to'
            'ich dziedzictwo.'.encode('utf-8', 'replace')).hexdigest(),
    )
    print('Prepared message:', msg)
    print('Sending to concent...')
    content = client.send_to_concent(msg, keys.raw_privkey, keys.raw_pubkey)
    print('-' * 80)
    print(content)


if __name__ == '__main__':
    common.config_logging(suffix='_concent')
    main()
