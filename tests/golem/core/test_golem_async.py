import asyncio
from unittest.mock import Mock, ANY

import pytest

from golem.core.golem_async import CallScheduler
from golem.task import requestedtaskmanager


class TestCallScheduler:

    @pytest.mark.asyncio
    async def test_schedule(self, monkeypatch):
        loop = Mock(time=Mock(return_value=10**8))
        monkeypatch.setattr(
            requestedtaskmanager.asyncio,
            'get_event_loop',
            Mock(return_value=loop))

        scheduler = CallScheduler()
        scheduler.schedule('fn', 1000., lambda: True)
        loop.call_at.assert_called_with(10**8 + 1000., ANY)

    @pytest.mark.asyncio
    async def test_reschedule(self, monkeypatch):
        cancel = Mock()
        monkeypatch.setattr(asyncio.TimerHandle, 'cancel', cancel)

        scheduler = CallScheduler()
        scheduler.schedule('fn', 1000., lambda: True)
        assert not cancel.called

        scheduler.schedule('fn2', 1000., lambda: True)
        assert not cancel.called

        scheduler.schedule('fn', 1., lambda: False)
        assert cancel.called
