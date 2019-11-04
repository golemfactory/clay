#!/usr/bin/env python3

import signal
import sys
from pathlib import Path

from mock import patch
from twisted.internet import defer, reactor

from golem.docker.client import local_client
from golem.envs import RuntimeStatus
from golem.envs.docker import DockerPrerequisites, DockerRuntimePayload
from golem.envs.docker.cpu import DockerCPUEnvironment, DockerCPUConfig


@defer.inlineCallbacks
def main(image, tag, command):
    patch('golem.envs.docker.cpu.Whitelist.is_whitelisted', return_value=True)\
        .start()
    env = DockerCPUEnvironment(DockerCPUConfig(work_dirs=[Path('.')]))
    yield env.prepare()
    yield env.install_prerequisites(DockerPrerequisites(
        image=image,
        tag=tag
    ))
    runtime = env.runtime(DockerRuntimePayload(
        image=image,
        tag=tag,
        env={},
        command=command
    ))

    @defer.inlineCallbacks
    def _stop(*_, **__):
        print('Stopping...')
        yield runtime.stop()

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    yield runtime.prepare()
    yield runtime.start()

    client = local_client()
    stream = client.stats(runtime._container_id, decode=True, stream=True)
    for stats in stream:
        # Container cannot be removed when the stream is being read and the
        # stream will not terminate until the container is removed.
        # Therefore an explicit status check and break is needed.
        if runtime.status() is not RuntimeStatus.RUNNING:
            break
        try:
            kernel = stats['cpu_stats']['cpu_usage']['usage_in_kernelmode']
            user = stats['cpu_stats']['cpu_usage']['usage_in_usermode']
            total = stats['cpu_stats']['cpu_usage']['total_usage']
            mem = stats['memory_stats']['usage']
            print(f'Kernel: {(kernel / 1000000000):.3f} s '
                  f'User: {(user / 1000000000):.3f} s '
                  f'Total: {(total / 1000000000):.3f} s '
                  f'Memory: {(mem / 1024 / 1024):.3f} MiB')
        except KeyError:
            # The last message in the stream usually raises KeyError
            print('Wrong stats format')

    print('Cleaning up...')
    yield runtime.wait_until_stopped()
    yield runtime.clean_up()
    yield env.clean_up()
    reactor.stop()


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <image>[:<tag>] <command>")
        sys.exit(1)
    try:
        image, tag = sys.argv[1].split(':')
    except ValueError:
        image, tag = sys.argv[1], 'latest'
    command = sys.argv[2]
    main(image, tag, command)
    reactor.run()
