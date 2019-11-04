import typing

from golem.task import ComputationType

if typing.TYPE_CHECKING:
    # pylint: disable=unused-import
    from golem_messages import message


class CannotComputeTask(Exception):
    def __init__(self, *args, **kwargs):
        self.reason: 'message.tasks.CannotComputeTask.REASON' = \
            kwargs.pop('reason')
        super().__init__(*args, **kwargs)

    def __str__(self):
        return f"{ self.__class__.__name__ } reason={ self.reason }"


class ComputationInProgress(Exception):
    def __init__(
            self,
            comp_type: ComputationType,
            comp_id: str
    ) -> None:
        super().__init__()
        self.comp_type = comp_type
        self.comp_id = comp_id

    def __str__(self):
        return f"{self.__class__.__name__}<{self.comp_type} id={self.comp_id}>"
