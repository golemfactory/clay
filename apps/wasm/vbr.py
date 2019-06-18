from abc import ABC, abstractmethod
from enum import IntEnum
from threading import Lock
from typing import Callable, Any, List, Tuple, Optional

class Actor:
    def __init__(self, uuid: str) -> None:
        self.uuid = uuid


class VerificationResult(IntEnum):
    SUCCESS = 0
    FAIL = 1
    UNDECIDED = 2


class NotAllowedError(Exception):
    pass


class MissingResultsError(Exception):
    pass


class UnknownActorError(Exception):
    pass


class VerificationByRedundancy(ABC):
    def __init__(self, redundancy_factor: int, comparator: Callable[[Any, Any], bool], *args, **kwargs) -> None:
        self.redundancy_factor = redundancy_factor
        # assert comparator.func_closure is None
        self.comparator = comparator

    @abstractmethod
    def add_actor(self, actor: Actor) -> None:
        """Caller informs class that this is the next actor he wants to assign to the next subtask.
        Raises:
            NotAllowedError -- Actor given by caller is not allowed to compute next task.
            MissingResultsError -- Raised when caller wants to add next actor but has already
            exhausted this method. Now the caller should provide results by `add_result` method.
        """
        pass

    @abstractmethod
    def add_result(self, actor: Actor, result: Optional[Any]) -> None:
        """Add a result for verification.
        If a task computation has failed for some reason then the caller should use this method with the
        result equal to None.
        When user has added a result for each actor it reported by `add_actor` a side effect might be
        the verdict being available or caller should continue adding actors and results.
        Arguments:
            actor {Actor} -- Actor who has computed the result
            result {Any} --  Computation result
        Raises:
            UnknownActorError - raised when caller deliver an actor that was not previously reported by `add_actor` call.
            ValueError - raised when attempting to add a result for some actor more than once
        """
        pass

    @abstractmethod
    def get_verdicts(self) -> Optional[List[Tuple[Actor, Any, VerificationResult]]]:
        """
        Returns:
            Optional[List[Any, Actor, VerificationResult]] -- If verification is resolved a list of 3-element
            tuples (actor, result reference, verification_result) is returned. A None is returned
            when verification has not been finished yet.
        """
        pass

class Bucket:
    """A bucket containing a key and some values. Values are comparable directly,
    keys only by the comparator supplied at bucket creation"""

    def __init__(self, comparator: Callable[[Any, Any], bool], key: Any, value: Optional[Any]) -> None:
        self.comparator = comparator
        self.key = key
        if value is None:
            self.values = []
        else:
            self.values = [value]

    def key_equals(self, key: Any) -> bool:
        return self.comparator(self.key, key)

    def try_add(self, key: Any, value: Any) -> bool:
        """If the keys match, add value to the bucket and return True.
        Otherwise return False"""
        if self.key_equals(key):
            self.values.append(value)
            return True
        return False

    def __len__(self):
        return len(self.values)


class BucketVerifier(VerificationByRedundancy):
    def __init__(self,
                 redundancy_factor: int,
                 comparator: Callable[[Any, Any], bool],
                 referee_count: int) -> None:
        super().__init__(redundancy_factor, comparator)
        self.actors = []
        self.results = {}
        self.more_actors_needed = True
        self.buckets = []
        self.verdicts = None
        self.normal_actor_count = redundancy_factor + 1
        self.referee_count = referee_count
        self.majority = (self.normal_actor_count + self.referee_count) // 2 + 1

    def add_actor(self, actor):
        if actor in self.actors:
            raise NotAllowedError

        if not self.more_actors_needed:
            raise MissingResultsError

        self.actors.append(actor)
        if len(self.actors) >= self.redundancy_factor + 1:
            self.more_actors_needed = False

    def add_result(self, actor: Actor, result: Optional[Any]) -> None:
        if actor not in self.actors:
            raise UnknownActorError

        if actor in self.results:
            raise ValueError

        self.results[actor] = result

        if result is not None:   # None represents no result, hence is not counted
            found = False
            for bucket in self.buckets:
                if bucket.try_add(key=result, value=actor):
                    found = True
                    break

            if not found:
                self.buckets.append(Bucket(self.comparator, key=result, value=actor))

        print(f'add_actor: {len(self.actors)} actors, {len(self.results)} results, {len(self.buckets)} buckets')
        self.compute_verdicts() # this will set self.more_actors_needed

    def get_verdicts(self) -> Optional[List[Tuple[Actor, Any, VerificationResult]]]:
        return self.verdicts

    def compute_verdicts(self) -> None:

        self.more_actors_needed = len(self.actors) < self.normal_actor_count

        if len(self.results) < self.normal_actor_count:
            self.verdicts = None
            return

        # Go through the buckets, looking for majority. If none found, maybe ask for a tie-breaker
        max_popularity = 0
        winners = None
        for bucket in self.buckets:
            max_popularity = max(max_popularity, len(bucket))
            if len(bucket) >= self.majority:
                winners = bucket.values
                break

        if winners:
            self.more_actors_needed = False
            success = VerificationResult.SUCCESS
            fail = VerificationResult.FAIL
            self.verdicts = [(actor, self.results[actor], success if actor in winners else fail) for actor in self.actors]
        elif self.majority - max_popularity <= self.referee_count:
            self.verdicts = None
            self.more_actors_needed = True
        else:
            self.verdicts = [(actor, self.results[actor], VerificationResult.UNDECIDED) for actor in self.actors]
            self.more_actors_needed = False


class SimpleSubtaskVerifier(VerificationByRedundancy):
    """Simple verification by redundancy: subtask is executed by 2 providers,
with a possible third if no decision can be reached based on the first 2."""

    def __init__(self,
                 redundancy_factor: int, comparator: Callable[[Any, Any], int]) -> None:
        super().__init__(redundancy_factor, comparator)
        self.actors = []
        self.results = {}
        self.more_actors_needed = True

    def add_actor(self, actor):
        if actor in self.actors:
            raise NotAllowedError

        if not self.more_actors_needed:
            raise MissingResultsError

        self.actors.append(actor)
        if len(self.actors) >= 2:
            self.more_actors_needed = False

    def add_result(self, actor: Actor, result: Optional[Any]) -> None:
        if actor not in self.actors:
            raise UnknownActorError

        if actor in self.results:
            raise ValueError

        self.results[actor] = result

    def get_verdicts(self) -> Optional[List[Tuple[Actor, Any, VerificationResult]]]:
        actor_cnt = len(self.actors)
        result_cnt = len(self.results.keys())

        # get_verdicts should only get called when all results have been added
        # calling it otherwise is a contract violation
        assert(actor_cnt == result_cnt)

        assert(actor_cnt <= 3)

        if actor_cnt < 2:
            return None

        verdict_undecided = [(a, self.results[a], VerificationResult.UNDECIDED) for a in self.actors]
        real_results = [(a, self.results[a]) for a in self.actors if self.results[a] is not None]
        reporting_actors = [r[0] for r in real_results]
        reported_results = [r[1] for r in real_results]


        if actor_cnt == 2:
            if len(real_results) == 0:
                return verdict_undecided # more actors won't help, giving up

            if len(real_results) == 1:
                self.more_actors_needed = True
                return None  # not enough real results, need more actors

        if actor_cnt > 2 and len(real_results) < 2:
            return verdict_undecided

        if len(real_results) == 2:
            a1, a2 = reporting_actors
            r1, r2 = reported_results

            if self.comparator(r1, r2) == 0:
                return [(a1, r1, VerificationResult.SUCCESS), (a2, r2, VerificationResult.SUCCESS)]
            else:
                if actor_cnt > 2:
                    return verdict_undecided # give up
                else:
                    self.more_actors_needed = True
                    return None # more actors needed
        else: # 3 real results
            a1, a2, a3 = reporting_actors
            r1, r2, r3 = real_results

            if self.comparator(r1, r2) == 0 and self.comparator(r2, r3) == 0 and self.comparator(r3, r1) == 0:
                return [(r[0], r[1], VerificationResult.SUCCESS) for r in real_results]

            for permutation in [(0,1,2), (0,2,1), (1,2,0)]:
                permuted_pairs = [real_results[i] for i in permutation]
                a1, a2, a3 = [p[0] for p in permuted_pairs]
                r1, r2, r3 = [p[1] for p in permuted_pairs]
                if self.comparator(r1, r2) == 0:  # r1 and r2 are equal, hence r3 differs
                    return[(a1, r1, VerificationResult.SUCCESS), (a2, r2, VerificationResult.SUCCESS), (a3, r3, VerificationResult.FAIL)]

            # Loop exit means there is no equal pair, hence all 3 are different
            return verdict_undecided # all 3 results different
