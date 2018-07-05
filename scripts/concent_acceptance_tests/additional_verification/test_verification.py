import binascii
import os
import time
from pathlib import Path

from unittest import mock

from golem_messages.factories.tasks import ComputeTaskDefFactory
from golem_messages.message import concents as concent_msg
from golem_messages.message import tasks as tasks_msg

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

    def perform_upload(self, request):
        response = self.provider_cfts.upload(request)
        self._log_concent_response(response)
        self.assertEqual(response.status_code, 200)

    def upload_files(self, ftt, resources_filename, results_filename):
        self.perform_upload(
            ConcentFileRequest(
                str(resources_filename),
                ftt,
                file_category=concent_msg.FileTransferToken.FileInfo.
                Category.resources
            )
        )

        self.perform_upload(
            ConcentFileRequest(
                str(results_filename),
                ftt,
                file_category=concent_msg.FileTransferToken.FileInfo.
                Category.results
            )
        )

    def init_srv_with_files(self, results_filename):
        price = self.init_deposits()
        rct_path = 'subtask_results_rejected__report_computed_task__'
        ttc_path = rct_path + 'task_to_compute__'
        srv = self.get_correct_srv(**{
            ttc_path + 'price': price,
            ttc_path + 'compute_task_def': self.get_ctd(),
            ttc_path + 'size': self.size(self.resources_filename),
            ttc_path + 'package_hash': self.hash(self.resources_filename),
            ttc_path + 'concent_enabled': True,
            rct_path + 'size': self.size(results_filename),
            rct_path + 'package_hash': self.hash(results_filename),
        })
        return srv

    def test_verify(self):
        srv = self.init_srv_with_files(self.results_filename)
        response = self.provider_send(srv)
        asrv = self.provider_load_response(response)
        self.assertIsInstance(asrv, concent_msg.AckSubtaskResultsVerify)

        ftt = asrv.file_transfer_token

        self.upload_files(ftt, self.resources_filename,
                          self.results_filename)

        verification_start = time.time()

        while time.time() < verification_start + self.TIMEOUT:
            response = self.provider_receive_oob()
            if response:
                self.assertIsInstance(response,
                                      concent_msg.SubtaskResultsSettled)
                self.assertSamePayload(
                    response.task_to_compute,
                    srv.subtask_results_rejected.
                    report_computed_task.task_to_compute
                )
                return
            time.sleep(self.INTERVAL)

        self.assertFalse(True, "Verification timed out")

    def test_verify_negative(self):
        srv = self.init_srv_with_files(self.results_corrupt_filename)
        response = self.provider_send(srv)
        asrv = self.provider_load_response(response)
        self.assertIsInstance(asrv, concent_msg.AckSubtaskResultsVerify)

        ftt = asrv.file_transfer_token

        self.upload_files(ftt, self.resources_filename,
                          self.results_corrupt_filename)
        verification_start = time.time()

        while time.time() < verification_start + self.TIMEOUT:
            response = self.provider_receive_oob()
            if response:
                self.assertIsInstance(response,
                                      tasks_msg.SubtaskResultsRejected)
                self.assertSamePayload(
                    response.report_computed_task,
                    srv.subtask_results_rejected.report_computed_task
                )
                return
            time.sleep(self.INTERVAL)

        self.assertFalse(True, "Verification timed out")
