import bisect
import logging
import math
import sys
import time
import weakref
from threading import RLock


logger = logging.getLogger(__name__)


CONTENDER_LIFETIME = 30  # s
WINDOW_DURATION_DEFAULT = 8  # s
WINDOW_DURATION_MIN = 1  # s
WINDOW_DURATION_MAX = 16  # s
WINDOW_DURATION_SCALE_FACTOR = 0.75  # divisor
WINNER_TIMEOUT = 10  # s


def median(values):
    sv = sorted(values)
    q, r = divmod(len(values), 2)
    if r:
        return sv[q]
    return sum(sv[q - 1:q + 1]) / 2.0


def sigmoid(x):
    return 1. / (1. + math.e ** -x)


class Contender(object):

    def __init__(self, id, session, req_msg, lifetime=CONTENDER_LIFETIME):

        self.id = id
        self.score = -1.0
        self._session = weakref.ref(session)

        self.created = time.time()
        self.lifetime = lifetime

        self.req_msg = req_msg
        # min performance -> max penalty by default
        self.performance = float(req_msg.get('perf_index', 0.0))
        # min trust -> max penalty by default
        self.reputation = float(req_msg.get('computing_trust', -1.0))
        # max price -> max penalty by default
        self.price = float(req_msg.get('price', sys.maxint))

    def __lt__(self, other):
        return bool(other) and self.score < other.score

    @property
    def session(self):
        return self._session()

    def is_old(self):
        return self.created + self.lifetime < time.time()

    def update_score(self, task_client, total_subtasks, ref_performance, ref_price, perf_to_price=0.5):

        total_subtasks = float(max(total_subtasks, 1))
        ref_performance = float(max(ref_performance, 1))
        ref_price = float(max(ref_price, 0))

        if task_client:
            accepted, rejected = task_client.accepted(), task_client.rejected()
        else:
            accepted, rejected = 0, 0

        if rejected:
            self.score = -rejected
        else:
            # higher perf => higher score
            perf_score = sigmoid(self.performance / ref_performance) * perf_to_price
            # lower price => higher score
            price_score = sigmoid(ref_price / self.price) * (1. - perf_to_price)
            # number of accepted subtasks to total tasks bonus
            sub_score = sigmoid(accepted / total_subtasks)
            #            <-1; 1>           <-1; 1>      <-1; 1>       <-1; 1>
            self.score = self.reputation + perf_score + price_score + sub_score  # - 1.


class Contest(object):

    def __init__(self, task, min_score):

        self.task = task
        self.total_subtasks = task.total_tasks
        self.min_score = min_score

        self.started = None
        self.winner = None
        self.winner_ack = False
        self.rounds = 0

        self.contenders = dict()
        self.ranks = list()

        self._lock = RLock()

        self.new_round()

    def get_contender(self, contender_id):
        with self._lock:
            return self.contenders.get(contender_id)

    def add_contender(self, contender_id, session, params):
        if contender_id not in self.contenders:
            with self._lock:
                self.contenders[contender_id] = Contender(contender_id, session, params)
                self._rank_contenders()

    def remove_contender(self, contender_id):
        with self._lock:
            removed = self.contenders.pop(contender_id, None)
            self._rank_contenders()
        return removed

    def new_round(self):
        self.started = time.time()
        self.winner = None
        self.winner_ack = False
        self.rounds += 1

        return self.extend_round()

    def extend_round(self):
        return self._remove_old_contenders() + self._remove_low_score_contenders()

    def _rank_contenders(self):

        ranks = list()
        performances = [c.performance for c in self.contenders.itervalues()]
        median_perf = median(performances) or 1.  # a reference level value; could be min or max

        for _id, contender in self.contenders.iteritems():

            node = self.task.counting_nodes.get(_id)
            contender.update_score(node, self.total_subtasks, median_perf, self.task.header.max_price)

            if not contender.is_old():
                bisect.insort_left(ranks, contender)

        self.ranks = ranks

    def _remove_old_contenders(self):

        new = dict()
        removed = list()

        with self._lock:

            for _id, contender in self.contenders.iteritems():
                if contender.is_old():
                    removed.append(contender)
                else:
                    new[_id] = contender

            self.contenders = new
            self._rank_contenders()

        return removed

    def _remove_low_score_contenders(self):

        removed = list()

        # ranks are sorted in asc order
        for contender in self.ranks:

            if contender.score < self.min_score:
                removed.append(contender)
                self.contenders.pop(contender.id, None)
            else:
                break

        self._rank_contenders()
        return removed


class ContestManager(object):

    def __init__(self, tasks, contest_duration, min_score=0.0):

        self.contest_duration = contest_duration
        self.min_score = min_score

        self._tasks = tasks
        self._contests = dict()
        self._checks = dict()
        self._announcements = dict()
        self._lock = RLock()
        self._reactor = None

    def add_contender(self, task_id, contender_id, session, params):

        task = self._tasks.get(task_id)
        create = task_id not in self._contests

        if create:
            self._contests[task_id] = Contest(task, self.min_score)

        self._contests[task_id].add_contender(contender_id, session, params)

        if create:
            self._check_later(task_id, timeout=self.contest_duration)

    def remove_contender(self, task_id, contender_id):
        contest = self._contests.get(task_id)
        if contest:
            if contest.winner and contest.winner.id == contender_id:
                contest.winner = None
            return contest.remove_contender(contender_id)

    def winner_acknowledgment(self, task_id, contender_id):
        contest = self._contests.get(task_id)
        if not contest:
            return

        winner = contest.winner

        if winner and winner.id == contender_id:
            self._cancel_announcement(task_id)
            self._get_reactor().callLater(0, winner.session.send_task_to_compute, winner.req_msg)

            to_remove = contest.new_round()
            self._remove_contenders(task_id, to_remove)
            self._check_later(task_id, self._calc_duration(contest))

            # no deferred announcements and checks at this point
            logger.debug("Contest round finished for task {}".format(task_id))

    def finish(self, task_id):
        logger.debug("Finishing contest for task {}".format(task_id))
        self._cancel_check(task_id)
        return self._contests.pop(task_id, None)

    def _check(self, task_id):

        contest = self._contests.get(task_id)
        if contest:
            # remove old + low score
            to_remove = contest.extend_round()
            self._remove_contenders(task_id, to_remove)

            if contest.ranks:
                # useful contenders left
                self._cancel_check(task_id)
                self._announce_winner(task_id)
                logger.debug("Contest round finished for task {}"
                             .format(task_id))
            else:
                # none of the contenders matches the criteria
                self._check_later(task_id, self._calc_duration(contest))
                logger.debug("Contenders' score below {}"
                             .format(self.min_score))
        else:
            # remove + cancel deferred checks
            self.finish(task_id)

    def _check_later(self, task_id, timeout):
        reactor = self._get_reactor()
        self._cancel_check(task_id)

        with self._lock:
            self._checks[task_id] = reactor.callLater(timeout, self._check, task_id)

    def _announce_winner(self, task_id, timed_out=False):
        self._cancel_announcement(task_id)

        contest = self._contests.get(task_id)

        if not contest:
            logger.error("No contest for task {}".format(task_id))

        elif not contest.ranks:
            logger.debug("No contenders for task {}".format(task_id))
            self._check_later(task_id, self._calc_duration(contest))

        else:
            reactor = self._get_reactor()

            winner = contest.remove_contender(contest.ranks[-1].id)
            contest.winner = winner

            logger.debug("Announcing round {} winner: {} (task {})"
                         .format(contest.rounds, winner.id, task_id))

            if winner.session:
                # we have an active task session
                reactor.callLater(0, winner.session.send_contest_winner, task_id)
                self._announcements[task_id] = reactor.callLater(WINNER_TIMEOUT, self._announce_winner,
                                                                 task_id, timed_out=True)
            else:
                # contestant disconnected; select another one
                reactor.callLater(0, self._announce_winner, task_id)

    def _remove_contenders(self, task_id, rejected, reason=None):
        logger.debug("Removing contenders for task {}: {}"
                     .format(task_id, [(c.id, c.score) for c in rejected]))

        reactor = self._get_reactor()

        for r in rejected:
            if r.session:
                reason = reason or "Contest elimination (score {}; min {})".format(r.score, self.min_score)
                reactor.callLater(0, r.session.send_cannot_assign_task, task_id, reason)
            else:
                logger.debug("No session for contender {} (task {})"
                             .format(r.id, task_id))

    def _calc_duration(self, contest):

        div = len(contest.ranks) or WINDOW_DURATION_SCALE_FACTOR
        duration = max(min(self.contest_duration / div, WINDOW_DURATION_MAX), WINDOW_DURATION_MIN)

        logger.debug("Contest window duration: {} (task {})".format(duration, contest.task.header.task_id))
        return duration

    def _cancel_check(self, task_id):
        return self._cancel_deferred(task_id, self._checks)

    def _cancel_announcement(self, task_id):
        return self._cancel_deferred(task_id, self._announcements)

    def _cancel_deferred(self, key, dictionary):
        with self._lock:
            d = dictionary.get(key)
            if d and d.active():
                d.cancel()
            return dictionary.pop(key, None)

    def _get_reactor(self):
        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor
        return self._reactor
