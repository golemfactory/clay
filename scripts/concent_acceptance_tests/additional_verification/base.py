import binascii
import os
import random
from pathlib import Path

from golem_messages import factories as msg_factories
from golem_messages.message import tasks as tasks_msg


from apps.blender.blenderenvironment import BlenderEnvironment

from golem.core.simplehash import SimpleHash

from ..base import SCIBaseTest


class SubtaskResultsVerifyBaseTest(SCIBaseTest):

    def setUp(self):
        super(SubtaskResultsVerifyBaseTest, self).setUp()
        self.env = BlenderEnvironment()

    def init_deposits(self):
        price = random.randint(1 << 20, 10 << 20)
        self.requestor_put_deposit(price)
        self.provider_put_deposit(price)
        return price

    @property
    def results_filename(self):
        return Path(__file__).parent / 'data/results.zip'

    @property
    def results_corrupt_filename(self):
        return Path(__file__).parent / 'data/results_corrupt.zip'

    @property
    def resources_filename(self):
        return Path(__file__).parent / 'data/resources'

    @staticmethod
    def size(filename):
        return os.path.getsize(filename)

    @staticmethod
    def hash(filename):
        return 'sha1:' + binascii.hexlify(
            SimpleHash.hash_file(filename)
        ).decode()

    @property
    def extra_data(self):
        return {
            "path_root": '',
            "start_task": 1,
            "total_tasks": 1,
            "scene_file": '/golem/resources/wlochaty3.blend',
            "frames": [1],
            "output_format": 'PNG',
            "resolution": [320, 240],
            "use_compositing": False,
            "samples": 0,
            "crops": [
                {
                    "outfilebasename": 'test task_1',
                    "borders_x": [0.0, 1.0],
                    "borders_y": [0.0, 1.0],
                }
            ]
        }

    def get_ctd(self, **kwargs):
        ctd = msg_factories.tasks.ComputeTaskDefFactory(
            docker_images=[
                di.to_dict() for di in self.env.docker_images],
            extra_data=self.extra_data,
            **kwargs,
        )
        return ctd

    def ttc_file_kwargs(self, ttc_path = ''):
        return {
            ttc_path + 'compute_task_def': self.get_ctd(),
            ttc_path + 'size': self.size(self.resources_filename),
            ttc_path + 'package_hash': self.hash(self.resources_filename),
            ttc_path + 'concent_enabled': True,
        }

    def rct_file_kwargs(self, results_filename=None):
        if not results_filename:
            results_filename = self.results_filename

        rct_path = 'subtask_results_rejected__report_computed_task__'
        return {
            rct_path + 'size': self.size(results_filename),
            rct_path + 'package_hash': self.hash(results_filename),
        }

    def get_srv(self, results_filename=None, **kwargs):
        rct_path = 'subtask_results_rejected__report_computed_task__'
        files_kwargs = self.rct_file_kwargs(results_filename=results_filename)

        ttc = self.gen_ttc(**self.ttc_file_kwargs())

        srv = msg_factories.concents.SubtaskResultsVerifyFactory(
            **self.gen_rtc_kwargs(rct_path),
            **{rct_path + 'task_to_compute': ttc},
            subtask_results_rejected__sign__privkey=self.requestor_priv_key,
            **files_kwargs,
            **kwargs,
        )
        srv.sign_concent_promissory_note(
            deposit_contract_address=
            self.ethereum_config.deposit_contract_address,
            private_key=self.provider_priv_key,
        )
        return srv

    def get_correct_srv(self, results_filename=None, **kwargs):
        vn = tasks_msg.SubtaskResultsRejected.REASON.VerificationNegative
        return self.get_srv(subtask_results_rejected__reason=vn,
                            results_filename=results_filename, **kwargs)

    def get_srv_with_deposit(self, results_filename=None, **kwargs):
        price = self.init_deposits()
        ttc_path = 'subtask_results_rejected__report_computed_task__' \
                   'task_to_compute__'
        kwargs.update({ttc_path + 'price': price})
        return self.get_correct_srv(results_filename=results_filename, **kwargs)
