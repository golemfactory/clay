from golem.docker.commands.docker import CommandDict, DockerCommandHandler


class DockerMachineCommandHandler(DockerCommandHandler):

    commands: CommandDict = dict(
        create=['docker-machine', '--native-ssh', 'create'],
        rm=['docker-machine', '--native-ssh', 'rm', '-y'],
        start=['docker-machine', '--native-ssh', 'start'],
        stop=['docker-machine', '--native-ssh', 'stop'],
        active=['docker-machine', '--native-ssh', 'active'],
        # DON'T use the '-q' option. It doesn't list VMs in invalid state
        list=['docker-machine', '--native-ssh', 'ls'],
        env=['docker-machine', '--native-ssh', 'env'],
        status=['docker-machine', '--native-ssh', 'status'],
        inspect=['docker-machine', '--native-ssh', 'inspect'],
        regenerate_certs=[
            'docker-machine', '--native-ssh', 'regenerate-certs', '--force'],
        restart=['docker-machine', '--native-ssh', 'restart'],
        execute=['docker-machine', '--native-ssh', 'ssh'],
        ip=['docker-machine', 'ip'],
    )

    commands.update(DockerCommandHandler.commands)
