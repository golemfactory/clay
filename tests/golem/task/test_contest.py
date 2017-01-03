import random
import sys
import time
import unittest

from mock import Mock, patch, ANY, call

from golem.network.transport.message import MessageWantToComputeTask
from golem.task.contest import ContestManager, Contender, Contest, WINNER_LIFETIME, median
from golem.task.taskclient import TaskClient


def _create_contender(node_name="node", perf_index=3000, price=2, computing_trust=0.0, session=True):

    request_message = MessageWantToComputeTask(node_name=node_name,
                                               perf_index=perf_index,
                                               price=price)

    contender_kwargs = dict(
        id=request_message.node_name,
        session=Mock() if session else None,
        computing_trust=computing_trust,
        request_message=request_message,
    )

    return Contender(**contender_kwargs), request_message, contender_kwargs


def _create_task(task_id="task_id", max_price=5, total_tasks=10):
    task = Mock()
    task.header.task_id = task_id
    task.header.max_price = max_price
    task.get_total_tasks.return_value = total_tasks
    task.counting_nodes.get.return_value = TaskClient("*")
    return task


def each(_coll, _fn):
    if _coll:
        for _elem in _coll:
            _fn(_elem)


class TestContender(unittest.TestCase):

    def test_init(self):

        def _assertions(_contender):
            assert _contender.score < 0
            assert _contender.created is not None
            assert _contender.session is not None
            assert isinstance(_contender.performance, float)
            assert isinstance(_contender.reputation, float)
            assert isinstance(_contender.price, float)

        contender, _, _ = _create_contender()
        _assertions(contender)

        contender, _, _ = _create_contender(perf_index=None, price=None, computing_trust=None)
        _assertions(contender)

        assert contender.performance == 0.
        assert contender.reputation == 0.
        assert contender.price == float(sys.maxint)

    def test_is_old(self):

        contender, _, _ = _create_contender()
        assert not contender.is_old()
        contender.created = time.time() - contender.lifetime - 1
        assert contender.is_old()
        contender.created = 0
        assert contender.is_old()

    def test_score(self):

        contender, _, _ = _create_contender()

        task_client = TaskClient("node")
        task_client._accepted = 1

        contender.update_score(task_client=None, total_subtasks=3, ref_performance=2000, ref_price=2)
        assert contender.score > 0
        contender.update_score(task_client=None, total_subtasks=3, ref_performance=3000, ref_price=3)
        assert contender.score > 0
        contender.update_score(task_client=task_client, total_subtasks=3, ref_performance=3000, ref_price=2)
        assert contender.score > 0
        contender.update_score(task_client=None, total_subtasks=3, ref_performance=3000, ref_price=2)
        assert contender.score == 0
        contender.update_score(task_client=None, total_subtasks=3, ref_performance=3000, ref_price=1)
        assert contender.score < 0
        contender.update_score(task_client=None, total_subtasks=3, ref_performance=4000, ref_price=2)
        assert contender.score < 0

        task_client._rejected = 1

        contender.update_score(task_client=task_client, total_subtasks=3, ref_performance=2000, ref_price=2)
        assert contender.score == -1
        contender.update_score(task_client=task_client, total_subtasks=3, ref_performance=10, ref_price=100)
        assert contender.score == -1


class TestContest(unittest.TestCase):

    @staticmethod
    def _create_contenders(i_m, n=3):
        return [
            _create_contender(node_name="node",
                              perf_index=1000 * i_m(i),
                              price=i_m(i),
                              computing_trust=i_m(i) / 10. - 0.5)[0]
            for i in xrange(0, n)
        ]

    def test_add_get_remove(self):
        _, contender_msg, contender_kwargs = _create_contender(node_name="name_1",
                                                               perf_index=2000,
                                                               price=2,
                                                               computing_trust=0)

        contest = Contest(task=Mock(), min_score=0.0)
        contest._rank_contenders = Mock()

        contender_kwargs['contender_id'] = contender_kwargs.pop('id')
        contest.add_contender(**contender_kwargs)
        assert "name_1" in contest.contenders
        assert len(contest.contenders) == 1
        assert contest._rank_contenders.called

        contender = contest.contenders["name_1"]
        contest._rank_contenders.called = False
        contest.add_contender(**contender_kwargs)

        assert "name_1" in contest.contenders
        assert len(contest.contenders) == 1
        assert not contest._rank_contenders.called
        assert contest.contenders["name_1"] is contender

        assert contest.get_contender("name_1") is contender
        assert contest.get_contender("id_2") is None

        contest._rank_contenders.called = False
        assert contest.remove_contender("name_1")
        assert contest._rank_contenders.called

        contest._rank_contenders.called = False
        assert not contest.remove_contender("name_1")
        assert not contest.remove_contender("id_2")
        assert not contest._rank_contenders.called

    def test_new_and_extend_round(self):

        contest = Contest(task=Mock(), min_score=0.0)
        contest._rank_contenders = Mock()
        contest._cleanup_contenders = Mock()

        assert contest.winner is None
        assert contest.started
        assert contest.rounds == 1

        started = contest.started
        contest.winner = Mock()

        contest._cleanup_contenders.called = False
        contest.extend_round()
        assert not contest._rank_contenders.called
        assert contest._cleanup_contenders.called
        assert contest.winner
        assert contest.rounds == 1
        assert contest.started == started

        contest._cleanup_contenders.called = False
        time.sleep(0.01)
        contest.new_round()
        assert not contest._rank_contenders.called
        assert contest._cleanup_contenders.called
        assert not contest.winner
        assert contest.rounds == 2
        assert contest.started > started

    def test_cleanup_contenders(self):

        contest = Contest(task=Mock(), min_score=0.0)
        contest._rank_contenders = Mock()

        batch_size = 3

        old = [
            _create_contender(node_name="old_{}".format(i),
                              perf_index=1000 * i,
                              price=i,
                              computing_trust=i / 10.)[0]
            for i in xrange(batch_size)
        ]
        each(old, lambda c: setattr(c, 'created', 0))

        neg_score = [
            _create_contender(node_name="neg_{}".format(i),
                              perf_index=1000 * i,
                              price=i * 10,
                              computing_trust=0.)[0]
            for i in xrange(batch_size)
        ]

        pos_score = [
            _create_contender(node_name="pos_{}".format(i),
                              perf_index=2000 * i,
                              price=i / 10.,
                              computing_trust=float(i+1) / batch_size)[0]
            for i in xrange(batch_size)
        ]

        concat = old + neg_score + pos_score
        random.shuffle(concat)

        contest.contenders = {c.id: c for c in concat}
        each(contest.contenders.values(),
             lambda c: c.update_score(task_client=None,
                                      total_subtasks=3,
                                      ref_performance=1500,
                                      ref_price=1.))

        removed = contest.extend_round()
        assert len(removed) == len(old) + len(neg_score)
        assert len(contest.contenders) == len(pos_score)
        assert contest._rank_contenders.called

    def test_rank_contenders(self):

        task = _create_task()
        contest = Contest(task, min_score=0.0)
        contenders = [
            _create_contender(node_name="contender_{}".format(i),
                              perf_index=1000 * i,
                              price=10 - i,
                              computing_trust=float(i / 10.) - 0.5)[0]
            for i in xrange(10)
        ]

        lowest_score = contenders[0]
        highest_score = contenders[-1]
        contest.contenders = {c.id: c for c in contenders}
        contest._rank_contenders()

        assert len(contest.ranks) == len(contenders)
        assert contest.ranks[0] is lowest_score
        assert contest.ranks[-1] is highest_score
        assert all(contest.ranks[i] <= contest.ranks[i+1] for i in range(len(contest.ranks) - 1))


class TestContestManager(unittest.TestCase):

    def setUp(self):
        super(TestContestManager, self).setUp()

        self.tasks = {}
        self.contest_duration = 3
        self.contest_manager = ContestManager(self.tasks, self.contest_duration)

    def test_add_remove_contender(self):

        cm = self.contest_manager
        cm._check_later = Mock()

        task = _create_task()

        contender_id = "id_1"
        task_id = task.header.task_id

        self.tasks[task_id] = task

        contender_msg = MessageWantToComputeTask(node_name="name_1",
                                                 perf_index=2000,
                                                 price=2)
        contender_kwargs = dict(
            contender_id=contender_id,
            session=Mock(),
            computing_trust=0,
            request_message=contender_msg,
        )

        cm.add_contender(task_id, **contender_kwargs)
        assert task_id in cm._contests
        assert len(cm._contests) == 1
        assert len(cm._contests[task_id].contenders) == 1
        assert cm._check_later.called

        contest = cm._contests[task_id]
        cm._check_later.called = False

        cm.add_contender(task_id, **contender_kwargs)
        assert cm._contests[task_id] is contest
        assert len(cm._contests) == 1
        assert len(contest.contenders) == 1
        assert not cm._check_later.called

        cm.remove_contender(task_id, contender_id)
        assert cm._contests[task_id] is contest
        assert len(cm._contests) == 1
        assert len(contest.contenders) == 0

        cm.add_contender(task_id, **contender_kwargs)
        contest = cm._contests[task_id]
        contender = contest.contenders.values()[0]
        contest.winner = contender

        cm.remove_contender(task_id, contender_id)
        assert not contest.winner

        cm.finish(task_id)
        assert task_id not in cm._contests
        assert len(cm._contests) == 0

    def test_calc_window_size(self):
        cm = self.contest_manager

        contest = Contest(task=Mock(), min_score=0.0)
        assert cm._calc_window_size(contest) > cm.contest_duration

        contest.ranks.append(Mock())
        assert cm._calc_window_size(contest) == cm.contest_duration

        contest.ranks.append(Mock())
        assert cm._calc_window_size(contest) < cm.contest_duration

    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_cancel_deferred(self, reactor):
        cm = self.contest_manager
        task_id = "task_id"

        cm._check_later(task_id, 0)
        assert cm._checks.values()[0]

        deferred = cm._cancel_check(task_id)
        assert deferred.cancel.called

        assert not cm._cancel_announcement(task_id)

    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_remove_contenders(self, reactor):
        cm = self.contest_manager
        task_id = "task_id"

        def create_rejected(with_session=False):
            r = Mock()
            if not with_session:
                r.session = None
            return r

        cm._remove_contenders(task_id, None)
        assert not reactor.callLater.called

        rejected_1 = [create_rejected() for _ in xrange(10)]

        cm._remove_contenders(task_id, rejected_1)
        assert not reactor.callLater.called

        rejected_2 = [create_rejected(True) for _ in xrange(10)]

        cm._remove_contenders(task_id, rejected_2)
        reactor.callLater.assert_called_with(0, ANY, task_id, ANY)

    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_announce_winner(self, reactor):
        cm = self.contest_manager
        task = _create_task()

        task_id = task.header.task_id
        self.tasks[task_id] = task

        _, contender_msg, contender_kwargs = _create_contender(node_name="id_1",
                                                               perf_index=2000,
                                                               price=2)

        # no task
        cm._announce_winner(task_id)
        assert not reactor.callLater.called

        contender_kwargs['contender_id'] = contender_kwargs.pop('id')
        cm.add_contender(task_id, **contender_kwargs)
        contest = cm._contests[task_id]
        contender = contest.contenders.values()[0]
        contest.ranks = [contender]

        cm._announce_winner(task_id)

        calls = [
            call(0, contender.session.send_task_to_compute, contender.req_msg),
        ]

        reactor.callLater.assert_has_calls(calls)

        cm.add_contender(task_id, **contender_kwargs)
        contest = cm._contests[task_id]
        contender = contest.contenders.values()[0]
        contest.ranks = [contender]

        # contender without session
        reactor.callLater.mock_calls = []
        session = Mock()
        session.return_value = None
        contender._session = session
        cm._announce_winner(task_id)

        calls = [
            call(0, cm._announce_winner, task_id),
        ]

        reactor.callLater.assert_has_calls(calls)

    @patch('twisted.internet.reactor', create=True, new_callable=Mock)
    def test_check(self, reactor):
        cm = self.contest_manager
        cm.finish = Mock()
        cm._check_later = Mock()
        cm._announce_winner = Mock()
        cm._remove_contenders = Mock()
        task = _create_task()

        task_id = task.header.task_id
        self.tasks[task_id] = task

        _, contender_msg, contender_kwargs = _create_contender(node_name="id_1",
                                                               perf_index=2000,
                                                               price=2)
        # no contest
        cm._check(task_id)
        assert cm.finish.called

        cm.finish.called = False

        # create contest
        contender_kwargs['contender_id'] = contender_kwargs.pop('id')
        cm.add_contender(task_id, **contender_kwargs)

        contest = cm._contests.values()[0]
        contest.extend_round = Mock()
        contest.ranks = []

        cm._check(task_id)
        assert not cm._announce_winner.called

        contender = contest.contenders.values()[0]
        contest.ranks = [contender]

        cm._check(task_id)
        assert cm._announce_winner.called


class TestMedian(unittest.TestCase):

    def test(self):
        assert median([4, 1, 3]) == 3
        assert median([4]) == 4
        assert median([]) == 0.0
        assert median([4, 3, 1, 2]) == 2.5
