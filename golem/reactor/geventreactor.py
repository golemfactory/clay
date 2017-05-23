## Copyright (C) 2011 by Jiang Yio <http://inportb.com/>
## Please find instructions at <http://wiki.inportb.com/python:geventreactor>
## The latest code is available at <https://gist.github.com/848058>
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

import gevent
import sys
import traceback
from bisect import insort

from gevent import Greenlet, GreenletExit, socket
from gevent.event import Event, AsyncResult
from gevent.pool import Group
from twisted.internet import defer, error, posixbase
from twisted.internet.base import IDelayedCall, ThreadedResolver
from twisted.internet.threads import _runMultiple
from twisted.persisted import styles
from twisted.python import log, failure, reflect, util
from twisted.python.runtime import seconds as runtimeSeconds
from zope.interface import Interface, implements

# Common exceptions raised by Stream
_NO_FILENO = error.ConnectionFdescWentAway('Handler has no fileno method')
_NO_FILEDESC = error.ConnectionFdescWentAway('Filedescriptor went away')

"""These (except for waitFor*) resemble the threading helpers from twisted.internet.threads"""


def deferToGreenletPool(*args, **kwargs):
    """Call function using a greenlet from the given pool and return the result as a Deferred"""
    reactor = args[0]
    pool = args[1]
    func = args[2]
    d = defer.Deferred()

    def task():
        try:
            reactor.callFromGreenlet(d.callback, func(*args[3:], **kwargs))
        except:
            reactor.callFromGreenlet(d.errback, failure.Failure())

    pool.add(Greenlet.spawn_later(0, task))
    return d


def deferToGreenlet(*args, **kwargs):
    """Call function using a greenlet and return the result as a Deferred"""
    from twisted.internet import reactor
    return deferToGreenletPool(reactor, reactor.getGreenletPool(), *args, **kwargs)


def callMultipleInGreenlet(tupleList):
    """Call a list of functions in the same thread"""
    from twisted.internet import reactor
    reactor.callInGreenlet(_runMultiple, tupleList)


def waitForGreenlet(g):
    """Link greenlet completion to Deferred"""
    d = defer.Deferred()

    def cb(g):
        try:
            d.callback(g.get())
        except:
            d.errback(failure.Failure())

    g.link(d)
    return d


def waitForDeferred(d, result=None):
    """Block current greenlet for Deferred, waiting until result is not a Deferred or a failure is encountered"""
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


def blockingCallFromGreenlet(*args, **kwargs):
    """Call function in reactor greenlet and block current greenlet waiting for the result"""
    reactor = args[0]
    func = args[1]
    result = AsyncResult()

    def task():
        try:
            result.set(func(*args[2:], **kwargs))
        except Exception, ex:
            result.set_exception(ex)

    reactor.callFromGreenlet(task)
    value = result.get()
    if isinstance(value, defer.Deferred):
        return waitForDeferred(value)
    else:
        return value


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

    def addToGreenletPool(self, g):
        pass


class Reschedule(Exception):
    """Event for IReactorTime"""
    pass


class GeventResolver(ThreadedResolver):
    """Based on ThreadedResolver, GeventResolver uses gevent to perform name lookups."""

    def getHostByName(self, name, timeout=(1, 3, 11, 45)):
        if timeout:
            timeoutDelay = sum(timeout)
        else:
            timeoutDelay = 60
        userDeferred = defer.Deferred()
        lookupDeferred = deferToGreenletPool(
            self.reactor, self.reactor.getGreenletPool(), socket.gethostbyname, name)
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
            del self.func, self.a, self.kw
            self.caller.cancelCallLater(self)

    def reset(self, secondsFromNow):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time = self.seconds() + secondsFromNow
            self.caller.callLater(self)

    def delay(self, secondsFromLater):
        if self.cancelled:
            raise error.AlreadyCancelled
        elif self.called:
            raise error.AlreadyCalled
        else:
            self.time += secondsFromLater
            self.caller.callLater(self)

    def active(self):
        return not (self.cancelled or self.called)

    def __le__(self, other):
        return self.time <= other.time

    def __lt__(self, other):
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
                L.append(', '.join(['%s=%s' % (k, reflect.safe_repr(v)) for (k, v) in self.kw.iteritems()]))
            L.append(')')
        if self.debug:
            L.append('\n\ntraceback at creation: \n\n%s' % ('    '.join(self.creator)))
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
        wait = {'doRead': socket.wait_read, 'doWrite': socket.wait_write}[method]
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
            except IOError:  # fix
                pass
            except AttributeError:  # fix
                pass
            except:
                why = sys.exc_info()[1]
                log.err()
        if why:
            try:
                self.reactor._disconnectSelectable(selectable, why, method == 'doRead')
            except AttributeError:
                pass
        if method == 'doRead':
            self.reactor.discardReader(selectable)
        else:
            self.reactor.discardWriter(selectable)


class GeventReactor(posixbase.PosixReactorBase):
    """Implement gevent-powered reactor based on PosixReactorBase."""
    implements(IReactorGreenlets)

    def __init__(self, *args):
        self.greenlet = None
        self.greenletpool = Group()
        self._reads = {}
        self._writes = {}
        self._callqueue = []
        self._wake = 0
        self._wait = 0
        self.resolver = GeventResolver(self)
        self.addToGreenletPool = self.greenletpool.add
        posixbase.PosixReactorBase.__init__(self, *args)
        self._initThreads()
        self._initThreadPool()
        self._initGreenletPool()

    def mainLoop(self):
        """This main loop yields to gevent until the end, handling function calls along the way."""
        self.greenlet = gevent.getcurrent()
        callqueue = self._callqueue
        seconds = self.seconds
        try:
            while 1:
                self._wait = 0
                now = seconds()
                if len(callqueue) > 0:
                    self._wake = delay = callqueue[0].time
                    delay -= now
                else:
                    self._wake = now + 300
                    delay = 300
                try:
                    self._wait = 1
                    gevent.sleep(max(0, delay))
                    self._wait = 0
                except Reschedule:
                    continue
                now = seconds()
                while 1:
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

    def addReader(self, selectable):
        """Add a FileDescriptor for notification of data available to read."""
        try:
            self._reads[selectable].resume()
        except KeyError:
            self._reads[selectable] = g = Stream.spawn(self, selectable, 'doRead')
            self.addToGreenletPool(g)

    def addWriter(self, selectable):
        """Add a FileDescriptor for notification of data available to write."""
        try:
            self._writes[selectable].resume()
        except KeyError:
            self._writes[selectable] = g = Stream.spawn(self, selectable, 'doWrite')
            self.addToGreenletPool(g)

    def removeReader(self, selectable):
        """Remove a FileDescriptor for notification of data available to read."""
        try:
            if selectable.disconnected:
                self._reads[selectable].kill(block=False)
                del self._reads[selectable]
            else:
                self._reads[selectable].pause()
        except KeyError:
            pass

    def removeWriter(self, selectable):
        """Remove a FileDescriptor for notification of data available to write."""
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

    def callLater(self, *args, **kw):
        if isinstance(args[0], DelayedCall):
            c = args[0]
            try:
                self._callqueue.remove(c)
            except ValueError:
                return None
        else:
            c = DelayedCall(self, self.seconds() + args[0], args[1], args[2:], kw, seconds=self.seconds)
        insort(self._callqueue, c)
        self.reschedule()
        return c

    def getDelayedCalls(self):
        return list(self._callqueue)

    def cancelCallLater(self, callID):  # deprecated
        self._callqueue.remove(callID)
        self.reschedule()

    # IReactorGreenlets
    def _initGreenletPool(self):
        self.greenletpoolShutdownID = self.addSystemEventTrigger('during', 'shutdown', self._stopGreenletPool)

    def _stopGreenletPool(self):
        self.greenletpool.kill()

    def getGreenletPool(self):
        return self.greenletpool

    def callInGreenlet(self, *args, **kwargs):
        self.addToGreenletPool(Greenlet.spawn_later(0, *args, **kwargs))

    def callFromGreenlet(self, *args, **kw):
        c = DelayedCall(self, self.seconds(), args[0], args[1:], kw, seconds=self.seconds)
        insort(self._callqueue, c)
        self.reschedule()
        return c

    def suggestGreenletPoolSize(self, size):
        pass

    def addToGreenletPool(self, g):
        self.greenletpool.add(g)

    # IReactorThreads
    def _initThreads(self):  # do not initialize ThreadedResolver, since we are using GeventResolver
        self.usingThreads = True

    callFromThread = callFromGreenlet

    # IReactorCore
    def stop(self):
        if self.threadpool:
            self._callqueue.insert(0, DelayedCall(self, 0, self._stopThreadPool, (), {}, seconds=self.seconds))
        if self.greenletpool:
            self._callqueue.insert(0, DelayedCall(self, 0, self._stopGreenletPool, (), {}, seconds=self.seconds))
        self._callqueue.insert(0, DelayedCall(self, 0, gevent.kill, (self.greenlet,), {}, seconds=self.seconds))

    def reschedule(self):
        if self._wait and len(self._callqueue) > 0 and self._callqueue[0].time < self._wake:
            gevent.kill(self.greenlet, Reschedule)
            self._wait = 0


def install():
    """Configure the twisted mainloop to be run using geventreactor."""
    reactor = GeventReactor()
    from twisted.internet.main import installReactor
    installReactor(reactor)


__all__ = ['deferToGreenletPool', 'deferToGreenlet', 'callMultipleInGreenlet', 'waitForGreenlet', 'waitForDeferred',
           'blockingCallFromGreenlet', 'IReactorGreenlets', 'GeventResolver', 'GeventReactor', 'install']
