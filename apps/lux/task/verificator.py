import logging
import os

from apps.core.task.verificator import SubtaskVerificationState
from apps.rendering.task.verificator import RenderingVerificator


logger = logging.getLogger("apps.lux")


class LuxRenderVerificator(RenderingVerificator):
    def __init__(self, *args, **kwargs):
        super(LuxRenderVerificator, self).__init__(*args, **kwargs)
        self.collected_file_names = dict()
        self.test_flm = None

    def verify(self, subtask_id, subtask_info, tr_files):
        if len(tr_files) == 0:
            return SubtaskVerificationState.WRONG_ANSWER

        for tr_file in tr_files:
            tr_file = os.path.normpath(tr_file)
            if tr_file.upper().endswith('.FLM'):
                if self.advance_verification:
                    if not os.path.isfile(self.test_flm):
                        logger.warning("Advanced verification set, but couldn't find test result!")
                        logger.warning("Skipping verification")
                    else:
                        if not self.merge_flm_files(tr_file, self.test_flm):
                            logger.info("Subtask " + str(subtask_id) + " rejected.")
                            return SubtaskVerificationState.WRONG_ANSWER

