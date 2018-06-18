from enum import Enum, auto

from golem.task.requirement import Support, Requirement, RequirementException, \
    registered


class RenderingEngine(Enum):
    CPU = auto()
    CUDA = auto()
    OPENCL = auto()


@registered
class RenderingEngineRequirement(Requirement):

    def __init__(self, engine: RenderingEngine) -> None:
        self.engine = engine

    @staticmethod
    def get_id():
        return 'RenderingEngine'

    @classmethod
    def interpret(cls, value: str) -> 'RenderingEngineRequirement':
        try:
            return RenderingEngineRequirement(RenderingEngine[value])
        except KeyError:
            raise RequirementException(f'{cls.__name__} does not recognize '
                                       '{value} as a valid requirement value')

    def serialize(self):
        return self.engine.name


# pylint: disable=too-few-public-methods
class RenderingEngineSupport(Support):
    def __init__(self, engine: RenderingEngine) -> None:
        self.engine = engine

    def satisfies(self, requirement: Requirement) -> bool:
        return isinstance(requirement, RenderingEngineRequirement) \
               and self.engine == requirement.engine
