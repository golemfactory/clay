""" Portable file locking.

This module creates common interface for file locking implemented differently
on Windows and Posix systems.

Based on article
https://www.safaribooksonline.com/library/view/python-cookbook/0596001673/ch04s25.html.

TODO: Consider using improved implementation:
https://github.com/WoLpH/portalocker/blob/develop/portalocker/portalocker.py
"""
import os

# Needs win32all to work on Windows.
if os.name == 'nt':
    import win32con
    import win32file
    from pywintypes import OVERLAPPED
    LOCK_EX = win32con.LOCKFILE_EXCLUSIVE_LOCK
    LOCK_SH = 0  # the default
    LOCK_NB = win32con.LOCKFILE_FAIL_IMMEDIATELY
    __overlapped = OVERLAPPED()

    def lock(file, flags):
        hfile = win32file._get_osfhandle(file.fileno())
        try:
            win32file.LockFileEx(hfile, flags, 0, -0x10000, __overlapped)
        except win32file.error as err:
            raise IOError(*err.args)

    def unlock(file):
        hfile = win32file._get_osfhandle(file.fileno())
        win32file.UnlockFileEx(hfile, 0, -0x10000, __overlapped)

elif os.name == 'posix':
    import fcntl
    from fcntl import LOCK_EX, LOCK_SH, LOCK_NB  # noqa

    def lock(file, flags):
        fcntl.flock(file.fileno(), flags)

    def unlock(file):
        fcntl.flock(file.fileno(), fcntl.LOCK_UN)
