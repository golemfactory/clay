import json
from pathlib import Path
from typing import Any, Dict, Optional

from golem.core.deferred import sync_wait
from golem.interface.command import group, command, Argument


@group(name="test_task",
       help="Manage testing tasks")
class TestTask:
    client: Any = None

    file_name = Argument(
        'file_name',
        help="Task file"
    )

    # @command decorator hates @staticmethod
    # therefore disable=no-self-use is required

    @command(argument=file_name,
             help="Run testing task. It accepts a file like 'tasks create'.")
    def run(self, file_name: str):  # pylint: disable=no-self-use
        jsondata = Path(file_name).read_text()
        dictionary = json.loads(jsondata)
        result: bool = sync_wait(TestTask.client.run_test_task(dictionary))
        if result:
            return "Success"
        return "Error"

    @command(help="Abort testing task")
    def abort(self):  # pylint: disable=no-self-use
        result: bool = sync_wait(TestTask.client.abort_test_task())
        if result:
            return "Success"
        return "There was no test task to abort"

    @command(help="Show testing status")
    def status(self):  # pylint: disable=no-self-use
        result: Optional[Dict[str, Any]] = sync_wait(
            TestTask.client.check_test_status())
        return str(result)
