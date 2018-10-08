from golem.docker.commands.docker import CommandDict, DockerCommandHandler


class DockerMachineCommandHandler(DockerCommandHandler):

    commands: CommandDict = dict(
        create=['docker-machine', 'create'],
        rm=['docker-machine', 'rm', '-y'],
        start=['docker-machine', 'restart'],
        stop=['docker-machine', 'stop'],
        active=['docker-machine', 'active'],
        list=['docker-machine', 'ls', '-q'],
        env=['docker-machine', 'env'],
        status=['docker-machine', 'status'],
        inspect=['docker-machine', 'inspect'],
        regenerate_certs=['docker-machine', 'regenerate-certs', '--force']
    )

    commands.update(DockerCommandHandler.commands)
