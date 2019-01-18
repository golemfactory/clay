from unittest import TestCase
from unittest.mock import Mock, patch, call

from golem_messages.factories.datastructures.tasks import TaskHeaderFactory
from golem_messages.message import WantToComputeTask, TaskToCompute, \
    ComputeTaskDef
from golem_messages import factories as msg_factories
from golem.task.taskproviderstats import ProviderStats, ProviderStatsManager


class TestProviderStats(TestCase):

    def test_init(self):
        stats = ProviderStats(
            provider_wtct_cnt=1,
            provider_ttc_cnt=2,
            provider_wtct_to_ttc_delay_sum=3,
            provider_wtct_to_ttc_cnt=4,
            provider_sra_cnt=5,
            provider_srr_cnt=6,
            provider_income_assigned_sum=7,
            provider_income_completed_sum=8,
            provider_income_paid_sum=9,
        )

        # The number of properties didn't change
        assert len(vars(stats)) == 9

        # The names of properties didn't change
        assert stats.provider_wtct_cnt == 1
        assert stats.provider_ttc_cnt == 2
        assert stats.provider_wtct_to_ttc_delay_sum == 3
        assert stats.provider_wtct_to_ttc_cnt == 4
        assert stats.provider_sra_cnt == 5
        assert stats.provider_srr_cnt == 6
        assert stats.provider_income_assigned_sum == 7
        assert stats.provider_income_completed_sum == 8
        assert stats.provider_income_paid_sum == 9


@patch('golem.task.taskproviderstats.ProviderTTCDelayTimers')
class TestProviderStatsManager(TestCase):
    # pylint: disable=no-member

    def setUp(self):
        with patch('golem.task.taskproviderstats.IntStatsKeeper'):
            self.manager = ProviderStatsManager()

    def test_on_message_invalid_arguments(self, _):
        manager = self.manager

        manager._on_message()
        assert not manager.keeper.increase_stat.called

        manager._on_message(event="sent")
        assert not manager.keeper.increase_stat.called

        manager._on_message(event="sent", message=Mock())
        assert not manager.keeper.increase_stat.called

    def test_on_wtct_message(self, _):
        manager = self.manager
        message = WantToComputeTask(task_header=TaskHeaderFactory())

        manager._on_message(event="sent", message=message)
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_wtct_cnt')

    def test_on_ttc_message(self, timers):
        manager = self.manager
        compute_task_def = ComputeTaskDef(task_id="deadbeef")
        message = TaskToCompute(compute_task_def=compute_task_def)

        # dt is not known
        manager.keeper.reset_mock()
        timers.time.return_value = None

        manager._on_message(event="received", message=message)
        manager.keeper.increase_stat.assert_called_once_with('provider_ttc_cnt')

        # dt is known
        manager.keeper.reset_mock()
        timers.time.return_value = 42

        calls = [
            call('provider_ttc_cnt'),
            call('provider_wtct_to_ttc_cnt'),
            call('provider_wtct_to_ttc_delay_sum', 42),
        ]

        manager._on_message(event="received", message=message)
        manager.keeper.increase_stat.assert_has_calls(calls)

    def test_on_sra_message(self, _):
        manager = self.manager
        sra = msg_factories.tasks.SubtaskResultsAcceptedFactory()

        manager._on_message(event='received', message=sra)
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_sra_cnt')

    def test_on_srr_message(self, _):
        manager = self.manager
        srr = msg_factories.tasks.SubtaskResultsRejectedFactory()

        manager._on_message(event='received', message=srr)
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_srr_cnt')

    def test_on_subtask_started_invalid_arguments(self, _):
        manager = self.manager

        manager._on_subtask_started()
        assert not manager.keeper.increase_stat.called

        manager._on_subtask_started(event='other')
        assert not manager.keeper.increase_stat.called

        with self.assertRaises(KeyError):
            manager._on_subtask_started(event='started')
        with self.assertRaises(TypeError):
            manager._on_subtask_started(event='started', price=None)
        with self.assertRaises(ValueError):
            manager._on_subtask_started(event='started', price="hello")

    def test_on_subtask_started(self, _):
        manager = self.manager
        manager._on_subtask_started(event='started', price="10")
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_income_assigned_sum', 10)

    def test_on_income_invalid_arguments(self, _):
        manager = self.manager

        manager._on_income()
        assert not manager.keeper.increase_stat.called

        manager._on_income(event='other')
        assert not manager.keeper.increase_stat.called

        with self.assertRaises(KeyError):
            manager._on_income(event='created')
        with self.assertRaises(TypeError):
            manager._on_income(event='created', amount=None)
        with self.assertRaises(ValueError):
            manager._on_income(event='created', amount="hello")

    def test_on_income(self, _):
        manager = self.manager

        manager._on_income(event='created', amount="11")
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_income_completed_sum', 11)

        manager.keeper.increase_stat.reset_mock()

        manager._on_income(event='confirmed', amount="22")
        manager.keeper.increase_stat.assert_called_once_with(
            'provider_income_paid_sum', 22)
