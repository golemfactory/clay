import bisect
import logging
import math
import sys
import time
import weakref
from threading import RLock

from golem.core.common import HandleKeyError

logger = logging.getLogger(__name__)


CONTENDER_LIFETIME = 600  # How many seconds should contender offer be valid

WINDOW_SIZE_DEFAULT = 30  # s Default contest duration length
WINDOW_SIZE_MIN = 0.5  # s Minium contest duration length
WINDOW_SIZE_MAX = 500  # s Maximum contest duration length
WINDOW_SIZE_INCREASE_FACTOR = 0.75  # divisor


def median(values):
    sv = sorted(values)
    q, r = divmod(len(values), 2)
    if r:
        return sv[q]
    return sum(sv[q - 1:q + 1]) / 2.0


def sigmoid(x):
    return 1. / (1. + math.e ** -x)


class Contender(object):
    """ Representation of provider's offer for specific task """

    _sigmoid_0 = sigmoid(0.)
    _sigmoid_1 = sigmoid(1.)

    def __init__(self, contender_id, session, request_message,
                 computing_trust=-1.0, lifetime=CONTENDER_LIFETIME):
        """
        Create new contender instace
        :param str contender_id: if of a provider
        :param TaskSession session: session kept with this contender
        :param MessageWantToComputeTask request_message: message that this contender sent
        :param float computing_trust: how much do we trust this contender
        :param float|int lifetime: for how many seconds should this offer be valid
        """
        self.id = contender_id
        self.score = -1.0
        self._session = weakref.ref(session)

        self.created = time.time()
        self.lifetime = lifetime

        self.req_msg = request_message
        # min performance -> max penalty by default
        self.performance = float(request_message.perf_index or 0.0)
        # neutral trust if unknown
        self.reputation = float(computing_trust or 0.0)
        # max price -> max penalty by default
        self.price = float(request_message.price or sys.maxint)

    def __lt__(self, other):
        return other and self.score < other.score

    def __eq__(self, other):
        return other and self.score == other.score

    def __ne__(self, other):
        return not self.__eq__(other)

    def __cmp__(self, other):
        if self < other:
            return -1
        elif self == other:
            return 0
        return 1

    @property
    def session(self):
        return self._session()

    def is_old(self):
        """
        Return True if this offer is no longer valid, False otherwise
        :return bool:
        """
        return self.created + self.lifetime < time.time()

    def update_score(self, task_client, total_subtasks, ref_performance,
                     ref_price, perf_to_price=0.5):
        """
        Compute new score for this contender. If the provider's subtask result for this task was
        rejected before, he gets a negative score.
        :param TaskClient task_client: information about node stats on this task
        :param num total_subtasks: how many subtasks are in this task
        :param float ref_performance: median of all performances declared by nodes
        :param float ref_price: max price per hour that can be used on this task
        :param float perf_to_price: performance to price importance ration
        :return float: score for this provider
        """
        total_subtasks = float(max(total_subtasks, 1))
        ref_performance = float(max(ref_performance, 1))
        ref_price = float(max(ref_price, 0))

        if task_client:
            accepted, rejected = task_client.accepted(), task_client.rejected()
        else:
            accepted, rejected = 0, 0

        if rejected:
            self.score = -rejected
            return

        perf_to_price = max(perf_to_price, 0.)
        price_to_perf = max(1. - perf_to_price, 0.)

        # higher perf => higher score
        perf_score = sigmoid(self.performance / ref_performance) * perf_to_price
        perf_zero = self._sigmoid_1 * perf_to_price
        # lower price => higher score
        price_score = sigmoid(ref_price / self.price) * price_to_perf
        price_zero = self._sigmoid_1 * price_to_perf
        # number of accepted subtasks to total tasks bonus
        sub_score = sigmoid(accepted / total_subtasks)
        sub_zero = self._sigmoid_0

        point_zero = perf_zero + price_zero + sub_zero
        #            <-1; 1>           <0; 1>       <0; 1>        <0; 1>
        self.score = self.reputation + perf_score + price_score + sub_score - point_zero

        logger.debug("Score: rep[{}] + perf[{}] + price[{}] + sub[{}] - {} = {} ({})"
                     .format(self.reputation, perf_score, price_score, sub_score, point_zero,
                             self.score, self.id))


class Contest(object):
    """ Contest for a given task, that should allow to choose the set of best providers
    """

    def __init__(self, task, min_score, perf_to_price=0.5):
        """
        Create a new Contestst instance
        :param Task task:
        :param float min_score: minimum score needed for provider to be chosen
        :param float perf_to_price: provider's performance to provider's price importance ratio
        """
        self.task = task
        self.total_subtasks = task.get_total_tasks()
        self.min_score = min_score
        self.perf_to_price = perf_to_price

        self.started = None
        self.winners = list()
        self.rounds = 0

        self.contenders = dict()
        self.ranks = list()

        self._lock = RLock()

        self.new_round()

    def get_contender(self, contender_id):
        """
        Return contender
        :param str contender_id: id of a contender
        :return Contender | None:
        """
        return self.contenders.get(contender_id)

    def add_contender(self, contender_id, session, request_message, computing_trust,
                      lifetime=CONTENDER_LIFETIME):
        """
        Add a new provider to the contest. Update scores for all contenders and put sorted scores
        in ranks.
        If provider already was in this contest - do nothing.
        :param str contender_id: if of a provider
        :param TaskSession session: session kept with this contender
        :param MessageWantToComputeTask request_message: message that this contender sent
        :param float computing_trust: How much do we trust this contender?
        :param float|int lifetime: How long is this offer valid?
        :return:
        """
        if contender_id not in self.contenders:
            with self._lock:
                self.contenders[contender_id] = Contender(contender_id, session, request_message,
                                                          computing_trust, lifetime)
                self._rank_contenders()

    def choose_winners(self, num):
        """ Choose set of a <num> winners, remove them from the contest and rank rest of the
        contenders. If there are less than <num> contender available, choose all of them. """
        with self._lock:
            self.winners = list()
            winners = self.ranks[-num:]
            for winner in winners:
                winner = self.contenders.pop(winner.id, None)
                if winner:
                    self.winners.append(winner)
            if self.winners:
                self._rank_contenders()

    def remove_contender(self, contender_id):
        """
        Remove provider from the contest. Update scores for all contenders.
         If he wasn't in the contest, do nothing.
        :param str contender_id: id of a provider
        :return:
        """
        with self._lock:
            removed = self.contenders.pop(contender_id, None)
            if removed:
                self._rank_contenders()
        return removed

    def new_round(self):
        self.started = time.time()
        self.winners = []
        self.rounds += 1

        return self.extend_round()

    def extend_round(self):
        return self._cleanup_contenders()

    def _rank_contenders(self):
        ranks = list()
        performances = [c.performance for c in self.contenders.itervalues()]
        median_perf = median(performances) or 1.  # a reference level value; could be min or max

        for _id, contender in self.contenders.iteritems():

            node = self.task.counting_nodes.get(_id)
            contender.update_score(node, self.total_subtasks, median_perf,
                                   self.task.header.max_price, self.perf_to_price)

            if not contender.is_old():
                bisect.insort_left(ranks, contender)

        self.ranks = ranks

    def _cleanup_contenders(self):

        new = dict()
        removed = list()

        with self._lock:

            for _id, contender in self.contenders.iteritems():
                # remove old and low score contenders
                if contender.is_old() or contender.score < self.min_score:
                    removed.append(contender)
                else:
                    new[_id] = contender

            self.contenders = new
            self._rank_contenders()

        return removed


def _log_key_error(*args, **_):
    logger.warning("No contest for task {}".format(args[1]))
    return False


class ContestManager(object):

    handle_key_error = HandleKeyError(_log_key_error)

    def __init__(self, tasks, contest_duration=WINDOW_SIZE_DEFAULT,
                 min_score=0.0):
        """
        Create new Contest Manager instance
        :param dict tasks: dictionary with existing tasks: key - task_id (str),
        value - Task.
        :param float|int contest_duration: contest duration in seconds
        :param float min_score: minimum score needed to accept provider
        """

        self.contest_duration = contest_duration
        self.min_score = min_score

        self._tasks = tasks
        self._contests = dict()
        self._checks = dict()
        self._lock = RLock()
        self._reactor = None

    def add_contender(self, task_id, contender_id, session, request_message, computing_trust):
        """
        Add information about new provider that wants to compute task. If
        the contest for given tasks wasn't created before, create it and add
        callLater method to check results.
        :param str task_id: id of task that given provider want to compute
        :param str contender_id: id of a provider
        :param TaskSession session: session with given provider
        :param MessageWantToComputeTask request_message: message that provider
         sent
        :param float computing_trust: How much do we trust this provider?
        :return:
        """

        task = self._tasks.get(task_id)
        create = task_id not in self._contests

        if create:
            self._contests[task_id] = Contest(task, self.min_score)

        self._contests[task_id].add_contender(contender_id, session, request_message,
                                              computing_trust)

        if create:
            self._check_later(task_id, timeout=self.contest_duration)

    @handle_key_error
    def remove_contender(self, task_id, contender_id):
        """
        Remove specific provider from the contest. If this provider was a winner, change winner
         to None.
        :param str task_id: id of a task / contest
        :param str contender_id: id of a provider
        :return:
        """
        contest = self._contests[task_id]
        for contender in contest.winners:
            if contender.id == contender_id:
                contest.winners.remove(contender)
                break
        return contest.remove_contender(contender_id)

    @handle_key_error
    def finish(self, task_id):
        """
        End the contest with given id, cancel deferred checks remove information about contest
        :param str task_id: id of a task
        :return Contest|None : information about contest or None (if contest with given id doesn't
         exist.
        """
        logger.debug("Contest finished for task {}".format(task_id))
        self._cancel_check(task_id)
        return self._contests.pop(task_id, None)

    def _check(self, task_id):

        contest = self._contests.get(task_id)
        if contest:

            to_remove = contest.extend_round()
            self._remove_contenders(task_id, to_remove)

            if contest.ranks:
                self._announce_winners(task_id)
            else:
                # none of the contenders meets the criteria
                self._check_later(task_id, self._calc_window_size(contest))
                logger.debug("Extending round {}: no contenders".format(contest.rounds))
        else:
            # remove + cancel deferred checks
            self.finish(task_id)

    def _check_later(self, task_id, timeout):
        reactor = self._get_reactor()
        self._cancel_check(task_id)

        with self._lock:
            self._checks[task_id] = reactor.callLater(timeout, self._check, task_id)

    @handle_key_error
    def _announce_winners(self, task_id):
        self._cancel_check(task_id)
        contest = self._contests[task_id]
        num_winners = max(contest.total_subtasks / 10, 1)

        if not contest.ranks:
            logger.debug("No contenders for task {}".format(task_id))
            self._check_later(task_id, self._calc_window_size(contest))
            return

        reactor = self._get_reactor()
        contest.choose_winners(num_winners)

        logger.debug("Announcing round {} winners: {} (task {})"
                     .format(contest.rounds, contest.winners, task_id))

        winner_found = False
        for winner in contest.winners:
            if winner.session:
                # we have an active task session
                reactor.callLater(0, winner.session.send_task_to_compute, winner.req_msg)

                winner_found = True

                # no deferred announcements and checks at this point
                logger.debug("Contest round {} winner for task {}: {} (score: {})"
                             .format(contest.rounds - 1, task_id, winner.id, winner.score))

        if not winner_found:
            # contestant disconnected; select another one
            reactor.callLater(0, self._announce_winners, task_id)
        else:
            to_remove = contest.new_round()
            self._remove_contenders(task_id, to_remove)
            self._check_later(task_id, self._calc_window_size(contest))

    def _remove_contenders(self, task_id, rejected, reason=None):
        if not rejected:
            return

        logger.debug("Removing contenders for task {}: {}"
                     .format(task_id, [(c.id, c.score) for c in rejected]))
        reactor = self._get_reactor()

        for r in rejected:
            if r.session:
                reason = reason or "Contest elimination (score {}; min {})".format(r.score, self.min_score)
                reactor.callLater(0, r.session.send_cannot_assign_task, task_id, reason)
            else:
                logger.debug("No session for contender {} (task {})".format(r.id, task_id))

    def _calc_window_size(self, contest):

        div = len(contest.ranks) or WINDOW_SIZE_INCREASE_FACTOR
        duration = min(self.contest_duration / div, WINDOW_SIZE_MAX)
        duration = max(duration, WINDOW_SIZE_MIN)

        logger.debug("Contest window duration: {} (task {})".format(duration, contest.task.header.task_id))
        return duration

    def _cancel_check(self, task_id):
        return self._cancel_deferred(task_id, self._checks)

    def _cancel_deferred(self, key, dictionary):
        with self._lock:
            d = dictionary.pop(key, None)
            if d and d.active():
                d.cancel()
            return d

    def _get_reactor(self):
        if not self._reactor:
            from twisted.internet import reactor
            self._reactor = reactor
        return self._reactor
