from golem.environments.environment import Environment


class DummyTestEnvironment(Environment):
    def __init(self):
        super().__init__()
        self.source_code_required = True

    @classmethod
    def get_id(cls):
        return "TEST_ENVIRONMENT"

    # pylint: disable=arguments-differ
    def get_task_thread(self, *_, **__):
        return None

    def get_benchmark(self):
        return None, None
