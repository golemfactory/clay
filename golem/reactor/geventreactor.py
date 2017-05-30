## Twisted reactor based on gevent
##
## Copyright (C) 2011-2013 by Jiang Yio <inportb@gmail.com>
## Copyright (C) 2012 by Matthias Urlichs <matthias@urlichs.de>
## Copyright (C) 2013 by Erik Allik <eallik@gmail.com>
##
## Permission is hereby granted, free of charge, to any person obtaining a copy
## of this software and associated documentation files (the "Software"), to deal
## in the Software without restriction, including without limitation the rights
## to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
## copies of the Software, and to permit persons to whom the Software is
## furnished to do so, subject to the following conditions:
##
## The above copyright notice and this permission notice shall be included in
## all copies or substantial portions of the Software.
##
## THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
## IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
## FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
## AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
## LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
## OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
## THE SOFTWARE.


import sys
import traceback
import warnings
from bisect import insort

import gevent
from gevent import Greenlet, GreenletExit, socket
from gevent.pool import Group
from gevent.event import Event, AsyncResult

from twisted.python import log, failure, reflect, util
from twisted.python.runtime import seconds as runtimeSeconds
from twisted.internet import defer, error, posixbase
from twisted.internet.base import IDelayedCall, ThreadedResolver
from twisted.internet.threads import deferToThreadPool, deferToThread, \
    callMultipleInThread, blockingCallFromThread
from twisted.persisted import styles

from zope.interface import Interface, implements


__all__ = [
    'deferToGreenletPool',
    'deferToGreenlet',
    'callMultipleInGreenlet',
    'waitForGreenlet',
    'waitForDeferred',
    'blockingCallFromGreenlet',
    'IReactorGreenlets',
    'GeventThreadPool',
    'GeventResolver',
    'GeventReactor',
    'install'
]


# Common exceptions raised by Stream
_NO_FILENO = error.ConnectionFdescWentAway('Handler has no fileno method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')


# Mirrored from twisted.internet.threads for backwards-compatibility
deferToGreenletPool = deferToThreadPool
deferToGreenlet = deferToThread
callMultipleInGreenlet = callMultipleInThread
blockingCallFromGreenlet = blockingCallFromThread


def waitForGreenlet(g):
    """Link greenlet completion to Deferred"""
    d = defer.Deferred()

    def cb(_g):
        try:
            d.callback(_g.get())
        except:
            d.errback(failure.Failure())

    g.link(cb)
    return d


def waitForDeferred(d,result=None):
    """Block current greenlet for Deferred, waiting until result is not 
    a Deferred or a failure is encountered"""
    if result is None:
        result = AsyncResult()

    def cb(res):
        if isinstance(res, defer.Deferred):
            waitForDeferred(res, result)
        else:
            result.set(res)

    def eb(res):
        result.set_exception(res)

    d.addCallbacks(cb, eb)
    try:
        return result.get()
    except failure.Failure, ex:
        ex.raiseException()


class IReactorGreenlets(Interface):
    """Interface for reactor supporting greenlets"""

    def getGreenletPool(self):
        pass

    def callInGreenlet(self, *args, **kwargs):
        pass

    def callFromGreenlet(self, *args, **kw):
        pass

    def suggestGreenletPoolSize(self, size):
        pass


class Reschedule(Exception):
    """Event for IReactorTime"""
    pass


class GeventThreadPool(Group):
    """This class allows Twisted to work with a greenlet pool"""

    def __init__(self, *args, **kwargs):
        Group.__init__(self, *args, **kwargs)
        self.open = True

    def start(self, greenlet=None):
        """Start the greenlet pool or add a greenlet to the pool."""
        if greenlet is not None:
            return Group.start(self,greenlet)

    def startAWorker(self):
        pass

    def stopAWorker(self):
        pass

    def callInThread(self, func, *args, **kwargs):
        """Call a callable object in a separate greenlet."""
        if self.open:
            self.add(Greenlet.spawn_later(0, func, *args, **kwargs))

    def callInThreadWithCallback(self, onResult, func, *args, **kwargs):
        """Call a callable object in a separate greenlet and call onResult
         with the return value."""
        if self.open:
            def task(*a, **kw):
                try:
                    res = func(*a, **kw)
                except:
                    onResult(False, failure.Failure())
                else:
                    onResult(True, res)
            self.add(Greenlet.spawn_later(0, task, *args, **kwargs))

    def stop(self):
        """Stop greenlet pool."""
        self.open = False
        self.kill(block=False)
        self.join()

    def adjustPoolsize(self, minthreads=None, maxthreads=None):
        pass


class GeventResolver(ThreadedResolver):
    """Based on ThreadedResolver, GeventResolver uses gevent 
    to perform name lookups."""

    def getHostByName(self, name, timeout=(1, 3, 11, 45)):
        if timeout:
            timeoutDelay = sum(timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
        lookupDeferred = deferToThreadPool(
            self.reactor, self.reactor.getThreadPool(),
            socket.gethostbyname, name)
        cancelCall = self.reactor.callLater(
            timeoutDelay, self._cleanup, name, lookupDeferred)
        self._runningQueries[lookupDeferred] = (userDeferred, cancelCall)
        lookupDeferred.addBoth(self._checkTimeout, name, lookupDeferred)
        return userDeferred


class DelayedCall(object):
    """Delayed call proxy for IReactorTime"""

    implements(IDelayedCall)
    debug = False
    _str = None

    def __init__(self, caller, time, func, a, kw, seconds=runtimeSeconds):
        self.caller = caller
        self.time = time
        self.func = func
        self.a = a
        self.kw = kw
        self.seconds = seconds
        self.cancelled = self.called = 0
        if self.debug:
            self.creator = traceback.format_stack()[:-2]

    def __call__(self):
        if not (self.called or self.cancelled):
            self.called = 1
            self.func(*self.a, **self.kw)
            del self.func, self.a, self.kw

    def getTime(self):
        return self.time

    def cancel(self):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.cancelled = 1
            if self.debug:
                self._str = str(self)
            del self.func,self.a,self.kw
            self.caller.cancelCallLater(self)

    def reset(self, secondsFromNow):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time = self.seconds() + secondsFromNow
            self.caller.scheduleDelayedCall(self)

    def delay(self, secondsFromLater):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time += secondsFromLater
            self.caller.scheduleDelayedCall(self)

    def active(self):
        return not (self.cancelled or self.called)

    def __le__(self,other):
        return self.time <= other.time

    def __lt__(self,other):
        return self.time < other.time

    def __str__(self):
        if self._str is not None:
            return self._str
        if hasattr(self, 'func'):
            if hasattr(self.func, 'func_name'):
                func = self.func.func_name
                if hasattr(self.func, 'im_class'):
                    func = self.func.im_class.__name__ + '.' + func
            else:
                func = reflect.safe_repr(self.func)
        else:
            func = None
        now = self.seconds()
        L = ['<DelayedCall 0x%x [%ss] called=%s cancelled=%s' % (
                util.unsignedID(self), self.time - now, self.called,
                self.cancelled)]
        if func is not None:
            L.extend((' ', func, '('))
            if self.a:
                L.append(', '.join([reflect.safe_repr(e) for e in self.a]))
                if self.kw:
                    L.append(', ')
            if self.kw:
                L.append(', '.join(['%s=%s' % (k, reflect.safe_repr(v))
                                    for (k, v) in self.kw.iteritems()]))
            L.append(')')
        if self.debug:
            L.append('\n\ntraceback at creation: \n\n%s'
                     % ('    '.join(self.creator)))
        L.append('>')
        return ''.join(L)


class Stream(Greenlet, styles.Ephemeral):

    def __init__(self, reactor, selectable, method):
        Greenlet.__init__(self)
        self.reactor = reactor
        self.selectable = selectable
        self.method = method
        self.wake = Event()
        self.wake.set()
        self.pause = self.wake.clear
        self.resume = self.wake.set

    def _run(self):
        selectable = self.selectable
        method = self.method
        wait = {
            'doRead': socket.wait_read,
            'doWrite': socket.wait_write
        }[method]
        try:
            fileno = selectable.fileno()
        except AttributeError:
            why = _NO_FILENO
        else:
            if fileno == -1:
                why = _NO_FILEDESC
            else:
                why = None
        if why is None:
            wake = self.wake.wait
            try:
                while wake():
                    wait(fileno)
                    why = getattr(selectable, method)()
                    if why:
                        break
            except GreenletExit:
                pass
            except IOError:    # fix
                pass
            except AttributeError: # fix
                pass
            except:
                why = sys.exc_info()[1]
                log.err()
        if why:
            try:
                self.reactor._disconnectSelectable(selectable, why,
                                                   method == 'doRead')
            except AttributeError:
                pass
        if method == 'doRead':
            self.reactor.discardReader(selectable)
        else:
            self.reactor.discardWriter(selectable)


class GeventReactor(posixbase.PosixReactorBase):
    """Implement gevent-powered reactor based on PosixReactorBase."""

    implements(IReactorGreenlets)

    def __init__(self, *args, **kwargs):
        self.resolver = None
        self.greenlet = None
        self.threadpool = None
        self._reads = {}
        self._writes = {}
        self._callqueue = []
        self._wake = 0
        self._wait = 0
        posixbase.PosixReactorBase.__init__(self, *args, **kwargs)

    def mainLoop(self, timeout=None):
        """This main loop yields to gevent until the end, handling function 
        calls along the way."""
        self.greenlet = gevent.getcurrent()
        callqueue = self._callqueue
        seconds = self.seconds
        start = seconds()
        if timeout is None:
            run = True
        else:
            run = False
        try:
            while run or timeout > seconds() - start:
                self._wait = 0
                now = seconds()
                if callqueue:
                    self._wake = delay = callqueue[0].time
                    delay -= now
                else:
                    self._wake = now+300
                    delay = 300
                try:
                    self._wait = 1
                    gevent.sleep(delay if delay > 0 else 0)
                except Reschedule:
                    continue
                finally:
                    self._wait = 0
                now = seconds()
                while run or timeout > seconds() - start:
                    try:
                        c = callqueue[0]
                    except IndexError:
                        break
                    if c.time <= now:
                        del callqueue[0]
                        try:
                            c()
                        except GreenletExit:
                            raise
                        except:
                            log.msg('Unexpected error in main loop.')
                            log.err()
                    else:
                        break
        except (GreenletExit, KeyboardInterrupt):
            pass
        log.msg('Main loop terminated.')
        self.fireSystemEvent('shutdown')

    doIteration = mainLoop

    def addReader(self, selectable):
        """Add a FileDescriptor for notification of data available to read."""
        try:
            self._reads[selectable].resume()
        except KeyError:
            self._reads[selectable] = g = Stream(self, selectable, 'doRead')
            g.start()
            self.threadpool.add(g)

    def addWriter(self, selectable):
        """Add a FileDescriptor for notification of data available to write."""
        try:
            self._writes[selectable].resume()
        except KeyError:
            self._writes[selectable] = g = Stream(self, selectable, 'doWrite')
            g.start()
            self.threadpool.add(g)

    def removeReader(self, selectable):
        """Remove a FileDescriptor for notification of data available 
        to read."""
        try:
            if selectable.disconnected:
                self._reads[selectable].kill(block=False)
                del self._reads[selectable]
            else:
                self._reads[selectable].pause()
        except KeyError:
            pass

    def removeWriter(self, selectable):
        """Remove a FileDescriptor for notification of data available 
        to write."""
        try:
            if selectable.disconnected:
                self._writes[selectable].kill(block=False)
                del self._writes[selectable]
            else:
                self._writes[selectable].pause()
        except KeyError:
            pass

    def discardReader(self, selectable):
        """Remove a FileDescriptor without checking."""
        try:
            del self._reads[selectable]
        except KeyError:
            pass

    def discardWriter(self, selectable):
        """Remove a FileDescriptor without checking."""
        try:
            del self._writes[selectable]
        except KeyError:
            pass

    def getReaders(self):
        return self._reads.keys()

    def getWriters(self):
        return self._writes.keys()

    def removeAll(self):
        return self._removeAll(self._reads, self._writes)

    # IReactorTime

    seconds = staticmethod(runtimeSeconds)

    def callLater(self, delay, func, *args, **kw):
        c = DelayedCall(self, self.seconds() + delay, func,
                        args, kw, seconds=self.seconds)
        insort(self._callqueue, c)
        self.reschedule()
        return c

    def getDelayedCalls(self):
        return list(self._callqueue)

    def cancelCallLater(self, callID):
        warnings.warn('GeventReactor.cancelCallLater is deprecated',
                      DeprecationWarning)
        self._callqueue.remove(callID)
        self.reschedule()

    # IReactorThreads

    def _initThreads(self):
        self.usingGreenlets = self.usingThreads = True
        if self.threadpool is None:
            self.resolver = GeventResolver(self)
            self.threadpool = GeventThreadPool()
            self.threadpoolShutdownID = self.addSystemEventTrigger(
                'during', 'shutdown', self._stopThreadPool)

    def _stopThreadPool(self):
        self.threadpoolShutdownID = None
        if self.threadpool is not None:
            self.threadpool.stop()
            self.threadpool = None

    def getThreadPool(self):
        return self.threadpool

    def callInThread(self, *args, **kwargs):
        self.threadpool.callInThread(*args, **kwargs)

    def callFromThread(self, func, *args, **kw):
        c = DelayedCall(self, self.seconds(), func,
                        args, kw, seconds=self.seconds)
        insort(self._callqueue, c)
        self.reschedule()
        return c

    def suggestThreadPoolSize(self, *args, **kwargs):
        pass

    # IReactorGreenlets, mirrored from IReactorThreads
    # for backwards-compatibility

    _initGreenlets = _initThreads
    _stopGreenletPool = _stopThreadPool
    getGreenletPool = getThreadPool
    callInGreenlet = callInThread
    callFromGreenlet = callFromThread
    suggestGreenletPoolSize = suggestThreadPoolSize

    # IReactorCore

    def stop(self):
        self._callqueue.insert(0, DelayedCall(self, 0, self._stopThreadPool,
                                              (), {}, seconds=self.seconds))
        self._callqueue.insert(0, DelayedCall(self, 0, self._stopGreenletPool,
                                              (), {}, seconds=self.seconds))
        self._callqueue.insert(0, DelayedCall(self, 0, gevent.kill,
                                              (self.greenlet,), {},
                                              seconds=self.seconds))

    def reschedule(self):
        if self._wait and self._callqueue and \
           self._callqueue[0].time < self._wake:
            gevent.kill(self.greenlet, Reschedule)

    def scheduleDelayedCall(self, c):
        try:
            self._callqueue.remove(c)
        except ValueError:
            pass
        insort(self._callqueue, c)
        self.reschedule()
        return c


def install():
    """Configure the twisted mainloop to be run using geventreactor."""
    reactor = GeventReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)
