from typing import Any

from golem_messages.message import WantToComputeTask, TaskToCompute
from golem_messages.message.tasks import SubtaskResultsAccepted, \
    SubtaskResultsRejected
from pydispatch import dispatcher

from golem.core.statskeeper import IntStatsKeeper
from golem.task.timer import ProviderTTCDelayTimers


class ProviderStats:

    def __init__(self, **kwargs) -> None:
        # WantToComputeTask count
        self.provider_wtct_cnt: int = 0
        # TaskToCompute count
        self.provider_ttc_cnt: int = 0
        # WantToComputeTask [tx] to TaskToCompute [rx] delta time
        self.provider_wtct_to_ttc_delay_sum: int = 0
        self.provider_wtct_to_ttc_cnt: int = 0
        # Verification messages count
        self.provider_sra_cnt: int = 0
        self.provider_srr_cnt: int = 0
        # Incomes
        self.provider_income_assigned_sum: int = 0
        self.provider_income_completed_sum: int = 0
        self.provider_income_paid_sum: int = 0

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ProviderStatsManager:

    def __init__(self) -> None:
        self.keeper = IntStatsKeeper(ProviderStats)

        dispatcher.connect(self._on_income,
                           signal="golem.income")
        dispatcher.connect(self._on_message,
                           signal="golem.message")
        dispatcher.connect(self._on_subtask_started,
                           signal="golem.subtask")

    # --- Message ---

    def _on_message(self, event: str = 'default', message: Any = None) -> None:
        if not message:
            return

        if event == 'sent' and isinstance(message, WantToComputeTask):
            self._on_wtct_message(message)
        elif event == 'received':
            if isinstance(message, TaskToCompute):
                self._on_ttc_message(message)
            elif isinstance(message, SubtaskResultsAccepted):
                self._on_sra_message()
            elif isinstance(message, SubtaskResultsRejected):
                self._on_srr_message()

    def _on_wtct_message(self, message: WantToComputeTask) -> None:
        ProviderTTCDelayTimers.start(message.task_id)
        self.keeper.increase_stat('provider_wtct_cnt')

    def _on_ttc_message(self, message: TaskToCompute) -> None:
        task_id = message.compute_task_def['task_id']

        ProviderTTCDelayTimers.finish(task_id)
        self.keeper.increase_stat('provider_ttc_cnt')

        dt = ProviderTTCDelayTimers.time(task_id)
        if dt is None:
            return

        self.keeper.increase_stat('provider_wtct_to_ttc_cnt')
        self.keeper.increase_stat('provider_wtct_to_ttc_delay_sum', dt)

    def _on_sra_message(self):
        self.keeper.increase_stat('provider_sra_cnt')

    def _on_srr_message(self):
        self.keeper.increase_stat('provider_srr_cnt')

    # --- Subtask ---

    def _on_subtask_started(self, event='default', **kwargs) -> None:
        if event == 'started':
            self.keeper.increase_stat('provider_income_assigned_sum',
                                      int(kwargs['price']))

    # --- Income ---

    def _on_income(self, event='default', **kwargs) -> None:
        if event == 'created':
            self.keeper.increase_stat('provider_income_completed_sum',
                                      int(kwargs['amount']))
        elif event == 'confirmed':
            self.keeper.increase_stat('provider_income_paid_sum',
                                      int(kwargs['amount']))

    def get_stats(self, name):
        return self.keeper.get_stats(name)
