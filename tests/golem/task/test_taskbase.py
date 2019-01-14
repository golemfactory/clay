from golem.task.taskbase import TaskBuilder


def test_build_definition() -> None:
    TaskBuilder.build_definition("testtask", {"resources": []})  # type: ignore
