from abc import ABC, abstractmethod
from typing import Type, List, Dict


class Requirement(ABC):
    """Class for representing requirements tasks place on environment
    Only environments satisfying all the requirements can compute the task"""

    @staticmethod
    @abstractmethod
    def get_id() -> str:
        """Globally unique id of this Requirement class"""
        pass

    @staticmethod
    @abstractmethod
    def interpret(value: str) -> 'Requirement':
        """Should unserialize string produced by :func:`~serialize` back
        into a Requirement object"""
        pass

    @abstractmethod
    def serialize(self) -> str:
        """This method should serialize the requirement into a string. Format
        of serialization is not pre-defined, the only requirement is that
        the method :func:`~interpret` must be able to parse that string back
        into this type of Requirement object"""
        pass


class RequirementException(Exception):
    pass


class RequirementRegistry:

    _register: Dict[str, Type[Requirement]] = {}

    @classmethod
    def register(cls, requirement_cls: Type[Requirement]):
        requirement_id = requirement_cls.get_id()
        cls._register[requirement_id] = requirement_cls

    @classmethod
    def ids(cls) -> List[str]:
        return list(cls._register.keys())

    @classmethod
    def get(cls, requirement_id: str) -> Type[Requirement]:
        try:
            return cls._register[requirement_id]
        except KeyError:
            raise RequirementException(f'Unknown requirement {requirement_id}')

    @classmethod
    def to_dict(cls, requirements: List) -> Dict[str, str]:
        """Returns dict of requirements in form
        {req_id: serialized_req}.
        """
        return {r.get_id(): r.serialize() for r in requirements}

    @classmethod
    def from_dict(cls, requirements: Dict[str, str]) -> List:
        """Deserializes a dict in form {req_id: serialized_req} into a list
        of Requirements. Can throw RequirementException"""
        return [cls.get(r_name).interpret(r_value)
                for (r_name, r_value) in requirements.items()]


def registered(cls):
    RequirementRegistry.register(cls)
    return cls


# pylint: disable=too-few-public-methods
class Support(ABC):
    """Class for representing a support for a given requirement.
    Environments can specify any number of supports."""

    @abstractmethod
    def satisfies(self, requirement: Requirement):
        pass
