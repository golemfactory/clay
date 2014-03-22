"""
File Locking
============

This module provides portable advisory file locking primitives that operate on
file descriptors. POSIX-like systems and Windows systems use different
primitives to perform file locking, and these different primitives are modeled
by incompatible (and different) modules in the Python standard library. This
module provides an abstract ``FileLock`` class, and underlying
implementations, to hide the operating system dependencies behind a simple
portable interface.

To create a file lock, simply instantiate the ``FileLock`` class with an open
file descriptor. It handles the rest:

.. python::

    from grizzled.io.filelock import FileLock

    fd = open('/tmp/lockfile', 'r+')
    lock = FileLock(fd)
    lock.acquire()

    ...

    lock.release()

You can also use the ``locked_file()`` function to simplify your code:

.. python::

    from grizzled.io.filelock import locked_file

    fd = open('/tmp/lockfile', 'r+')
    with locked_file(fd):
        ...
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
from contextlib import contextmanager

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['FileLock', 'locked_file']

LOCK_CLASSES = {'posix' : '_PosixFileLock',
                'nt'    : '_WindowsFileLock'}

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class FileLock(object):
    """
    A ``FileLock`` object models a file lock. It wraps a file descriptor
    and contains methods to acquire and release a lock on the file.

    File lock implementations that implement this interface are guaranteed
    to be advisory, but not mandatory, file locks. (They may, in fact, also
    be mandatory file locks, but they are not guaranteed to be.)

    Currently, there are underlying implementations for both POSIX systems
    and Windows.
    """

    def __init__(self, fd):
        """
        Allocate a new file lock that operates on the specified file
        descriptor.

        :Parameters:
            fd : int
                Open file descriptor. The file must be opened for writing or
                updating, not reading.
        """
        try:
            cls = eval(LOCK_CLASSES[os.name])
            self.lock = cls(fd)

        except KeyError:
            raise NotImplementedError, \
                  '''Don't know how to lock files on "%s" systems.''' % os.name

    def acquire(self, no_wait=False):
        """
        Lock the associated file. If someone already has the file locked,
        this method will suspend the calling process, unless ``no_wait`` is
        ``True``.

        :Parameters:
            no_wait : bool
                If ``False``, then ``acquire()`` will suspend the calling
                process if someone has the file locked. If ``True``, then
                ``acquire()`` will raise an ``IOError`` if the file is
                locked by someone else.

        :raise IOError: If the file cannot be locked for any reason.
        """
        self.lock.acquire(no_wait)

    def release(self):
        """
        Unlock (i.e., release the lock on) the associated file.
        """
        self.lock.release()

class _PosixFileLock(object):
    """File lock implementation for POSIX-compliant systems."""

    def __init__(self, fd):
        self.fd = fd

    def acquire(self, no_wait=False):
        import fcntl
        flags = fcntl.LOCK_EX
        if no_wait:
            flags |= fcntl.LOCK_NB

        fcntl.lockf(self.fd, flags)

    def release(self):
        import fcntl
        fcntl.lockf(self.fd, fcntl.LOCK_UN)

class _WindowsFileLock(object):
    """File lock implementation for Windows systems."""

    def __init__(self, fd):
        self.fd = fd

    def lock(self, no_wait=False):
        import msvcrt
        if no_wait:
            op = msvcrt.LK_NBLCK
        else:
            op = msvcrt.LK_LOCK

        self.fd.seek(0)
        msvcrt.locking(self.fd, op, 1)

    def unlock(self):
        import msvcrt
        self.fd.seek(0)
        msvcrt.locking(self.fd, LK_UNLCK, 1)

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

@contextmanager
def locked_file(fd, no_wait=False):
    """
    This function is intended to be used as a ``with`` statement context
    manager. It wraps a ``FileLock`` object so that the locking and unlocking
    of the file descriptor are automatic. With the ``locked_file()`` function,
    you can replace this code:
    
    .. python::

        lock = FileLock(fd)
        lock.acquire()
        try:
            do_something()
        finally:
            lock.release()

    with this code:
    
    .. python::

        with locked_file(fd):
            do_something()

    :Parameters:
        fd : int
            Open file descriptor. The file must be opened for writing
            or updating, not reading.
        no_wait : bool
            If ``False``, then ``locked_file()`` will suspend the calling
            process if someone has the file locked. If ``True``, then
            ``locked_file()`` will raise an ``IOError`` if the file is
            locked by someone else.
    """
    locked = False
    try:
        lock = FileLock(fd)
        lock.acquire(no_wait)
        locked = True
        yield lock
    finally:
        if locked:
            lock.release()
