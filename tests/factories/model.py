import factory

from golem import model
# pylint: disable=too-few-public-methods


class Income(factory.Factory):
    class Meta:
        model = model.Income

    sender_node = factory.Faker('binary', length=64)
    subtask = factory.Faker('uuid4')
    value = factory.Faker('pyint')
