import sys


def run_playbook(playbook_cls):
    playbook = playbook_cls.start()
    if playbook.exit_code:
        print("exit code", playbook.exit_code)
    sys.exit(playbook.exit_code)
