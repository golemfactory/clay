import binascii
import os
import time
from pathlib import Path

from unittest import mock

from golem_messages.factories.tasks import ComputeTaskDefFactory
from golem_messages.message import concents as concent_msg

from apps.blender.blenderenvironment import BlenderEnvironment
from apps.blender.resources.scenefileeditor import generate_blender_crop_file

from golem.core.simplehash import SimpleHash
from golem.network.concent.filetransfers import (
    ConcentFiletransferService, ConcentFileRequest
)

from .base import SubtaskResultsVerifyBaseTest


class SubtaskResultsVerifyFiletransferTest(SubtaskResultsVerifyBaseTest):
    TIMEOUT = 300
    INTERVAL = 10

    def setUp(self):
        super(SubtaskResultsVerifyBaseTest, self).setUp()
        self.provider_cfts = ConcentFiletransferService(
            keys_auth=mock.Mock(
                public_key=self.provider_pub_key,
                _private_key=self.provider_priv_key
            ),
            variant=self.variant,
        )
        self.env = BlenderEnvironment()

    @property
    def src_code(self):
        self.main_program_file = self.env.main_program_file
        with open(self.main_program_file, "r") as src_file:
            return src_file.read()

    @property
    def extra_data(self):
        return {
            "path_root": '',
            "start_task": 1,
            "end_task": 1,
            "total_tasks": 1,
            "outfilebasename": 'test task',
            "scene_file": '/golem/resources/wlochaty3.blend',
            "script_src": generate_blender_crop_file(
                (320, 240), (0.0, 1.0), (0.0, 1.0), False, 0),
            "frames": [1],
            "output_format": 'PNG',
        }

    def get_ctd(self, **kwargs):
        ctd = ComputeTaskDefFactory(
            docker_images=[
                di.to_dict() for di in self.env.docker_images],
            src_code=self.src_code,
            extra_data=self.extra_data,
            **kwargs,
        )
        return ctd

    @property
    def results_filename(self):
        return Path(__file__).parent / 'data/results.zip'

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

    def test_verify(self):
        price = self.init_deposits()
        rct_path = 'subtask_results_rejected__report_computed_task__'
        ttc_path = rct_path + 'task_to_compute__'
        srv = self.get_correct_srv(**{
            ttc_path + 'price': price,
            ttc_path + 'compute_task_def': self.get_ctd(),
            ttc_path + 'size': self.size(self.resources_filename),
            ttc_path + 'package_hash': self.hash(self.resources_filename),
            ttc_path + 'concent_enabled': True,
            rct_path + 'size': self.size(self.results_filename),
            rct_path + 'package_hash': self.hash(self.results_filename),
        })

        response = self.provider_send(srv)
        asrv = self.provider_load_response(response)
        self.assertIsInstance(asrv, concent_msg.AckSubtaskResultsVerify)

        ftt = asrv.file_transfer_token

        resources_request = ConcentFileRequest(
            str(self.resources_filename),
            ftt,
            file_category=concent_msg.FileTransferToken.FileInfo.
                Category.resources)
        response = self.provider_cfts.upload(resources_request)
        self._log_concent_response(response)
        self.assertEqual(response.status_code, 200)

        results_request = ConcentFileRequest(
            str(self.results_filename),
            ftt,
            file_category=concent_msg.FileTransferToken.FileInfo.
                Category.results)
        response = self.provider_cfts.upload(results_request)
        self._log_concent_response(response)
        self.assertEqual(response.status_code, 200)

        verification_start = time.time()

        #while time.time() < verification_start + self.TIMEOUT:
        #
        #    time.sleep(self.INTERVAL)