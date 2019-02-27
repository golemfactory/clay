from golem.docker.commands.docker import CommandDict, DockerCommandHandler


class DockerMachineCommandHandler(DockerCommandHandler):

    commands: CommandDict = dict(
        create=['docker-machine', '--native-ssh', 'create'],
        rm=['docker-machine', '--native-ssh', 'rm', '-y'],
        start=['docker-machine', '--native-ssh', 'start'],
        stop=['docker-machine', '--native-ssh', 'stop'],
        active=['docker-machine', '--native-ssh', 'active'],
        list=['docker-machine', '--native-ssh', 'ls', '-q'],
        env=['docker-machine', '--native-ssh', 'env'],
        status=['docker-machine', '--native-ssh', 'status'],
        inspect=['docker-machine', '--native-ssh', 'inspect'],
        regenerate_certs=[
            'docker-machine', '--native-ssh', 'regenerate-certs', '--force'],
        restart=['docker-machine', '--native-ssh', 'restart'],
        execute=['docker-machine', '--native-ssh', 'ssh'],
    )

    commands.update(DockerCommandHandler.commands)
