#!/usr/bin/env python
import mock

from golemapp import main  # noqa: E402 module level import not at top of file

with mock.patch("golem.task.taskserver.TaskServer.should_accept_provider",
                mock.Mock(return_value=True)):
    main()
