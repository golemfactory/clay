import random

from golem_messages import factories as msg_factories
from golem_messages.message import tasks as tasks_msg

from ..base import ConcentDepositBaseTest


class SubtaskResultsVerifyBaseTest(ConcentDepositBaseTest):

    def get_srv(self, **kwargs):
        rct_path = 'subtask_results_rejected__report_computed_task__'
        return msg_factories.concents.SubtaskResultsVerifyFactory(
            **self.gen_rtc_kwargs(rct_path),
            **self.gen_ttc_kwargs(rct_path + 'task_to_compute__'),
            subtask_results_rejected__sign__privkey=self.requestor_priv_key,
            **kwargs,
        )

    def get_correct_srv(self, **kwargs):
        vn = tasks_msg.SubtaskResultsRejected.REASON.VerificationNegative
        return self.get_srv(subtask_results_rejected__reason=vn, **kwargs)

    def init_deposits(self):
        price = random.randint(1 << 20, 10 << 20)
        self.requestor_put_deposit(price)
        self.provider_put_deposit(price)
        return price
