#Copyright (C) 2011 by Saul Ibarra Corretge
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in
#all copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
#THE SOFTWARE.

__all__ = ['set_nonblocking', 'close_fd', 'SharedPoll']

import os
import pyuv


def set_nonblocking(fd):
    import fcntl
    flags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)


def close_fd(fd):
    try:
        os.close(fd)
    except Exception:
        pass


class SharedPoll(object):
    """A shared poll handle.

    This is like pyuv.Poll, but multiple instances can be active
    for the same file descriptor.
    """

    def __init__(self, loop, fd):
        self.loop = loop
        try:
            poll = loop._poll_handles[fd]
        except KeyError:
            poll = pyuv.Poll(loop, fd)
            poll._count = 0
            poll._events = 0
            poll._readers = []
            poll._writers = []
            loop._poll_handles[fd] = poll
        poll._count += 1
        self._poll = poll
        self._events = 0
        self._callback = None
        self._closed = False

    @property
    def active(self):
        if self._closed or not self._callback:
            return False
        return self._poll.active

    @property
    def fileno(self):
        if self._closed:
            return -1
        return self._poll.fileno()

    def start(self, events, callback):
        if self._events:
            self.stop()
        self._events = events
        self._callback = callback
        if events & pyuv.UV_READABLE:
            self._poll._readers.append(callback)
        if events & pyuv.UV_WRITABLE:
            self._poll._writers.append(callback)
        self._adjust()

    def stop(self):
        if not self._callback:
            return
        if self._events & pyuv.UV_READABLE:
            self._poll._readers.remove(self._callback)
        if self._events & pyuv.UV_WRITABLE:
            self._poll._writers.remove(self._callback)
        self._events = 0
        self._callback = None
        self._adjust()

    def close(self):
        if self._closed:
            return
        self._poll._count -= 1
        self.stop()
        if self._poll._count > 0:
            return
        del self.loop._poll_handles[self._poll.fileno()]
        self._poll.close()
        self._poll = None
        self.loop = None
        self._closed = True

    def _adjust(self):
        mask = 0
        if self._poll._readers:
            mask |= pyuv.UV_READABLE
        if self._poll._writers:
            mask |= pyuv.UV_WRITABLE
        if mask and mask != self._poll._events:
            self._poll._events = mask
            self._poll.start(mask, self._poll_callback)
        elif not mask and mask != self._poll._events:
            self._poll._events = mask
            self._poll.stop()

    def ref(self):
        raise NotImplementedError

    def unref(self):
        raise NotImplementedError

    def __del__(self):
        self.close()

    @staticmethod
    def _poll_callback(handle, events, errorno):
        if errorno is not None:
            # Signal both readability and writability so that the error can be detected
            for callback in handle._readers:
                callback()
            for callback in handle._writers:
                callback()
            return
        if events & pyuv.UV_READABLE:
            for callback in handle._readers:
                callback()
        if events & pyuv.UV_WRITABLE:
            for callback in handle._writers:
                callback()
