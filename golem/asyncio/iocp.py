import asyncio
import select
import socket
import sys
import win32gui
from asyncio import ProactorEventLoop, events
from errno import EINTR
from threading import Thread
from win32event import MsgWaitForMultipleObjects, QS_ALLINPUT, WAIT_TIMEOUT, \
    WAIT_OBJECT_0, CreateEvent
from win32file import FD_CLOSE, WSAEnumNetworkEvents, WSAEventSelect, FD_READ, \
    FD_ACCEPT, FD_CONNECT

from devp2p import slogging
from tulipcore import IoWatcher

log = slogging.get_logger('iocp')
main_loop = None


# Patched version of Watcher._invoke; start and stop methods will be executed
# at different stages than in original implementation
def _invoke(self):
    if not self.active:
        return

    self.pending = False
    # noinspection PyBroadException
    try:
        # noinspection PyCallingNonCallable
        if self.args:
            self.callback(*self.args)
        else:
            self.callback()
    except Exception:
        raise
    except:
        self.loop.handle_error(self, *sys.exc_info())


IoWatcher._invoke = _invoke


# Based on twisted.internet.selectreactor.win32select
def win32select(r, w, _, timeout=None):
    if not (r or w):
        return [], [], []

    if timeout is None or timeout > 0.5:
        timeout = 0.5

    r, w, e = select.select(r, w, w, timeout)
    return r, w + e, []


class DescriptorWrapper:

    __slots__ = ['fno', 'cb']

    def __init__(self, fno, cb):
        self.fno = fno
        self.cb = cb

    def fileno(self):
        return self.fno

    def __str__(self):
        return 'FileDescriptor<fileno {}, id {}>'.format(self.fno, id(self))


class Win32EventLoop:
    """
    Code of this class is derived from
        twisted.internet.win32eventreactor.Win32Reactor

    Changes:
        - a hybrid of socket read events and selects for writes
        - runs in a separate thread with an asyncio event loop
        - does not manage files and their state
    """

    dummy_event = CreateEvent(None, 0, 0, None)

    def __init__(self):
        self._events = dict()
        self._reads = dict()
        self._reads_fno = dict()
        self._writes = dict()
        self._writes_fno = dict()

        self._thread = None
        self._task = None
        self._running = False

    @property
    def running(self):
        return self._running

    def start(self):
        global main_loop
        main_loop = asyncio.get_event_loop()

        self._thread = Thread(target=self._do_start)
        self._thread.daemon = True
        self._thread.start()
        self._running = True

    def stop(self):
        if self._task and not (self._task.cancelled() or self._task.done()):
            self._task.cancel()
            self._running = False

    def _do_start(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._loop())

    async def _loop(self, timeout=250):
        while self._running:
            await self._iteration(timeout)

    async def _iteration(self, timeout):
        timeout_s = timeout / 1000

        if not (self._events or self._writes):
            return await asyncio.sleep(0.1)

        self._select_writes(timeout_s)

        loop = asyncio.get_event_loop()
        handles = list(self._events.keys()) or [self.dummy_event]
        val = MsgWaitForMultipleObjects(handles, 0, timeout, QS_ALLINPUT)

        if val == WAIT_TIMEOUT:
            return

        elif val == WAIT_OBJECT_0 + len(handles):

            if win32gui.PumpWaitingMessages():
                loop.call_soon(0, self.stop)

        elif WAIT_OBJECT_0 <= val < WAIT_OBJECT_0 + len(handles):

            event = handles[val - WAIT_OBJECT_0]
            fd = self._events.get(event)

            if fd and fd in self._reads:
                fno = fd.fileno()

                try:
                    events = WSAEnumNetworkEvents(fno, event)
                    dispose = FD_CLOSE in events
                except Exception as exc:
                    log.error('WSAEnumNetworkEvents error:', exc)
                    dispose = True

                if dispose:
                    self.remove_reader(fd)

                main_loop.call_soon_threadsafe(fd.cb)

    def add_reader(self, reader):
        if reader not in self._reads:
            flags = FD_READ | FD_ACCEPT | FD_CONNECT | FD_CLOSE
            self._reads[reader] = self._create_socket_event(reader, flags)
            self._reads_fno[reader.fileno()] = reader

    def add_writer(self, writer):
        if writer not in self._writes:
            self._writes[writer] = 1
            self._writes_fno[writer.fileno()] = writer

    def remove_reader(self, reader):
        if reader in self._reads:
            self._events.pop(self._reads[reader], None)
            self._reads.pop(reader, None)
        self._reads_fno.pop(reader.fileno(), None)

    def remove_writer(self, writer):
        self._writes.pop(writer, None)
        self._writes_fno.pop(writer.fileno(), None)

    def _create_socket_event(self, fno, why):
        event = CreateEvent(None, 0, 0, None)
        WSAEventSelect(fno, event, why)
        self._events[event] = fno
        return event

    def _select_writes(self, timeout):
        writeable = []

        try:
            _, writeable, _ = win32select([], self._writes, [], timeout)
        except ValueError as err:
            log.error('select ValueError', err)
            return
        except TypeError as err:
            log.error('select TypeError', err)
            return
        except (select.error, socket.error, IOError) as se:
            log.error('select error', se)
            # select(2) encountered an error, perhaps while calling the fileno()
            # method of a socket.
            if se.args[0] in (0, 2):
                if not self._writes:
                    return
                raise
            elif se.args[0] == EINTR:
                pass
            elif se.args[0] == socket.EBADF:
                pass
            else:
                raise

        if writeable:
            for fno in writeable:
                fd = self._writes_fno.get(fno)
                if fd:
                    main_loop.call_soon_threadsafe(fd.cb)


class ProactorWin32EventsEventLoop(ProactorEventLoop):

    def __init__(self, proactor=None):
        ProactorEventLoop.__init__(self, proactor)

        self._dw_readers = dict()
        self._dw_writers = dict()

        self._win32_events = Win32EventLoop()

    def add_reader(self, fno, callback, *args):
        fd = DescriptorWrapper(fno, callback)
        self._start_if_needed()
        self._dw_readers[fno] = fd
        self._win32_events.add_reader(fd)

    def remove_reader(self, fno):
        self._start_if_needed()
        fd = self._dw_readers.pop(fno)
        self._win32_events.remove_reader(fd)

    def add_writer(self, fno, callback, *args):
        self._start_if_needed()
        fd = DescriptorWrapper(fno, callback)
        self._dw_writers[fno] = fd
        self._win32_events.add_writer(fd)

    def remove_writer(self, fno):
        self._start_if_needed()
        fd = self._dw_writers.pop(fno)
        self._win32_events.remove_writer(fd)

    def _start_if_needed(self):
        if not self._win32_events.running:
            self._win32_events.start()


class WindowsProactorEventLoopPolicy(events.BaseDefaultEventLoopPolicy):
    _loop_factory = ProactorWin32EventsEventLoop
