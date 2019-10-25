from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Callable, Any, List, Tuple, Optional, Dict


class Actor:
    def __init__(self, uuid: str) -> None:
        self.uuid = uuid

    def __eq__(self, other):
        return self.uuid == other.uuid

    def __hash__(self):
        return hash(self.uuid)


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


class AlreadyFinished(Exception):
    pass


class VerificationByRedundancy(ABC):
    def __init__(self, redundancy_factor: int,
                 comparator: Callable[[Any, Any], bool],
                 *_args, **_kwargs) -> None:
        self.redundancy_factor = redundancy_factor
        # assert comparator.func_closure is None
        self.comparator = comparator

    @abstractmethod
    def add_actor(self, actor: Actor) -> None:
        """Caller informs class that this is the next actor he wants to assign
        to the next subtask.
        Raises:
            NotAllowedError -- Actor given by caller is not allowed to compute
            next task.
            MissingResultsError -- Raised when caller wants to add next actor
            but has already.
            exhausted this method. Now the caller should provide results
            by `add_result` method.
        """
        pass

    @abstractmethod
    def add_result(self, actor: Actor, result: Optional[Any]) -> None:
        """Add a result for verification.
        If a task computation has failed for some reason then the caller
        should use this method with the result equal to None.
        When user has added a result for each actor it reported by `add_actor`
        a side effect might be the verdict being available or caller should
        continue adding actors and results.
        Arguments:
            actor {Actor} -- Actor who has computed the result
            result {Any} --  Computation result
        Raises:
            UnknownActorError - raised when caller deliver an actor that was
            not previously reported by `add_actor` call.
            ValueError - raised when attempting to add a result for some actor
            more than once.
        """
        pass

    @abstractmethod
    def get_verdicts(self) -> Optional[List[Tuple[Actor, Any,
                                                  VerificationResult]]]:
        """
        Returns:
            Optional[List[Any, Actor, VerificationResult]] -- If verification
            is resolved a list of 3-element tuples (actor, result reference,
            verification_result) is returned. A None is returned when
            verification has not been finished yet.
        """
        pass

    @abstractmethod
    def validate_actor(self, actor):
        """Validates whether given actor is acceptable

        Arguments:
            actor {[type]} -- Actor to be validated
        """
        pass


class Bucket:
    """A bucket containing a key and some values. Values are comparable
    directly, keys only by the comparator supplied at bucket creation"""

    def __init__(self, comparator: Callable[[Any, Any], bool], key: Any,
                 value: Optional[Any]) -> None:
        self.comparator = comparator
        self.key = key
        if value is None:
            self.values: List[Any] = []
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


# pylint:disable=too-many-instance-attributes
class BucketVerifier(VerificationByRedundancy):
    def __init__(self,
                 redundancy_factor: int,
                 comparator: Callable[[Any, Any], bool],
                 referee_count: int) -> None:
        super().__init__(redundancy_factor, comparator)
        self.actors: List[Actor] = []
        self.results: Dict[Actor, Any] = {}
        self.more_actors_needed = True
        self.buckets: List[Bucket] = []
        self.verdicts: Optional[List[Tuple[Actor, Any, VerificationResult]]]\
            = None
        self.normal_actor_count = redundancy_factor + 1
        self.referee_count = referee_count
        self.majority = (self.normal_actor_count + self.referee_count) // 2 + 1
        self.max_actor_cnt = self.normal_actor_count + self.referee_count

    def validate_actor(self, actor):
        if actor in self.actors:
            raise NotAllowedError

        if not self.more_actors_needed:
            raise MissingResultsError

    def add_actor(self, actor):
        self.validate_actor(actor)
        self.actors.append(actor)
        if len(self.actors) >= self.redundancy_factor + 1:
            self.more_actors_needed = False

    def remove_actor(self, actor):
        if self.verdicts is not None or actor in self.results.keys():
            raise AlreadyFinished
        self.actors.remove(actor)
        if len(self.actors) < self.redundancy_factor + 1:
            self.more_actors_needed = True

    def add_result(self, actor: Actor, result: Optional[Any]) -> None:
        if actor not in self.actors:
            raise UnknownActorError

        if actor in self.results:
            raise ValueError

        self.results[actor] = result

        # None represents no result, hence is not counted
        if result is not None:
            found = False
            for bucket in self.buckets:
                if bucket.try_add(key=result, value=actor):
                    found = True
                    break

            if not found:
                self.buckets.append(
                    Bucket(self.comparator, key=result, value=actor)
                )
        # this will set self.more_actors_needed
        self.compute_verdicts()

    def get_verdicts(self) -> Optional[List[Tuple[Actor, Any,
                                                  VerificationResult]]]:
        return self.verdicts

    def compute_verdicts(self) -> None:

        self.more_actors_needed = len(self.actors) < self.normal_actor_count

        if len(self.results) < self.normal_actor_count:
            self.verdicts = None
            return

        # Go through the buckets, looking for majority. If none found,
        # maybe ask for a tie-breaker.
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
            self.verdicts = [
                (actor, self.results[actor], success
                 if actor in winners else fail)
                for actor in self.actors
            ]
        elif self.majority - max_popularity <= self.referee_count and \
                len(self.actors) < self.max_actor_cnt:
            self.verdicts = None
            self.more_actors_needed = True
        else:
            self.verdicts = [
                (actor, self.results[actor], VerificationResult.UNDECIDED)
                for actor in self.actors]
            self.more_actors_needed = False
