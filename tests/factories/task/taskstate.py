import time

import factory

from golem.task import taskstate


class SubtaskState(factory.Factory):
    class Meta:
        model = taskstate.SubtaskState

    node_id = '0xadbeef' + 'deadbeef' * 15
    subtask_id = factory.Faker('uuid4')
    deadline = factory.LazyFunction(
        lambda: int(time.time()) + 10,
    )
    price = factory.Faker('random_int', min=10, max=50)
