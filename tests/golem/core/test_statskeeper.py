from golem.core.statskeeper import IntStatsKeeper
from golem.task.taskcomputer import CompStats
from golem.tools.testwithdatabase import TestWithDatabase


class TestStatsKeeper(TestWithDatabase):
    @staticmethod
    def _compare_stats(stat_keeper, stats):
        assert [stat_keeper.global_stats.computed_tasks,
                stat_keeper.global_stats.tasks_with_timeout,
                stat_keeper.global_stats.tasks_with_errors,
                stat_keeper.session_stats.computed_tasks,
                stat_keeper.session_stats.tasks_with_timeout,
                stat_keeper.session_stats.tasks_with_errors] == stats

    def test_stats_keeper(self):
        st = IntStatsKeeper(CompStats)
        assert isinstance(st, IntStatsKeeper)
        self._compare_stats(st, [0] * 6)

        st.increase_stat("computed_tasks")
        self._compare_stats(st, [1, 0, 0] * 2)
        st.increase_stat("computed_tasks")
        self._compare_stats(st, [2, 0, 0] * 2)
        st.increase_stat("computed_tasks")
        self._compare_stats(st, [3, 0, 0] * 2)

        st2 = IntStatsKeeper(CompStats)
        self._compare_stats(st2, [3] + [0] * 5)
        st2.increase_stat("computed_tasks")
        self._compare_stats(st2, [4, 0, 0, 1, 0, 0])
        st2.increase_stat("computed_tasks")
        self._compare_stats(st2, [5, 0, 0, 2, 0, 0])
        st.increase_stat("computed_tasks")
        self._compare_stats(st, [6, 0, 0, 4, 0, 0])