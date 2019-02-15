import os
import pathlib
import subprocess

from ..helpers import get_testdir


class NodeTestBase:
    def setUp(self):
        test_dir = pathlib.Path(get_testdir()) / self._relative_id()
        self.provider_datadir = test_dir / 'provider'
        self.requestor_datadir = test_dir / 'requestor'
        os.makedirs(self.provider_datadir)
        os.makedirs(self.requestor_datadir)

    def _relative_id(self):
        from . import __name__ as parent_name
        return self.id().replace(parent_name + '.', '')

    def _run_test(self, playbook_class_path: str, *args, **kwargs):
        cwd = pathlib.Path(os.path.realpath(__file__)).parent.parent
        test_args = [
            str(cwd / 'run_test.py'),
            playbook_class_path,
            *args,
            '--provider-datadir', self.provider_datadir,
            '--requestor-datadir', self.requestor_datadir,
        ]
        for k, v in kwargs.items():
            test_args.append('--' + k)
            test_args.append(v)

        return subprocess.call(args=test_args)
