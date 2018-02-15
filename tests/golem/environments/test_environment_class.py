from golem.environments.environment import Environment


class DummyTestEnvironment(Environment):
    @classmethod
    def get_id(cls):
        """ Get Environment unique id
        :return str:
        """
        return "TEST_ENVIRONMENT"

    # pylint: disable=arguments-differ
    def get_task_thread(self, *_, **__):
        return None

    def get_benchmark(self):
        return None, None
