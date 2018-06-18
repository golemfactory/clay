from golem.environments.environment import Environment


class DummyTestEnvironment(Environment):
    def __init__(self):
        super().__init__()
        self.source_code_required = True
        self.accept_tasks = True

    def get_id(self):
        return "TEST_ENVIRONMENT"

    # pylint: disable=arguments-differ
    def get_task_thread(self, *_, **__):
        return None

    def get_benchmark(self):
        return None, None
