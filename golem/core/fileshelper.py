import ctypes
import logging
import os
import shutil
import subprocess

from golem.core.common import is_windows
from golem.tools import memoryhelper

logger = logging.getLogger(__name__)


def copy_file_tree(src, dst, exclude=None):
    """Copy directory and it's content from src to dst. Doesn't copy files
       with extensions from excluded. Don't remove additional files from
       destination directory.
    :param str src: source directory (copy this directory)
    :param str dst: destination directory (copy source directory here)
    :param list|None exclude: don't copy files with this extensions
    """
    if exclude is None:
        exclude = []
    if not os.path.isdir(dst):
        os.mkdir(dst)
    for src_dir, dirs, files in os.walk(src):
        dst_dir = src_dir.replace(src, dst)
        if not os.path.exists(dst_dir):
            os.mkdir(dst_dir)
        for file_ in files:
            _, ext = os.path.splitext(file_)
            if ext in exclude:
                continue
            src_file = os.path.join(src_dir, file_)
            dst_file = os.path.join(dst_dir, file_)
            if os.path.exists(dst_file):
                os.remove(dst_file)
            shutil.copy2(src_file, dst_dir)


def get_dir_size(dir_, report_error=lambda _: ()):
    """Returns the size of the given directory and it's contents, in bytes.
    Similar to the Linux command `du -b`. In particular, returns non-zero
    for an empty dir.
    :param str dir_: directory name
    :param report_error: callable used to report errors
    :return int: size of directory and it's content
    """
    size = os.path.getsize(dir_)
    try:
        files = os.listdir(dir_)
    except OSError as err:
        report_error(err)
        files = []

    for el in files:
        path = os.path.join(dir_, el)
        if os.path.isfile(path):
            try:
                size += os.path.getsize(path)
            except OSError as err:
                report_error(err)
        elif os.path.isdir(path):
            size += get_dir_size(path, report_error)
    return size


def common_dir(arr, ign_case=None):
    """
    Returns a common directory for paths
    :param arr: Array of paths
    :param ign_case: Ignore case in paths
    :return: Common directory prefix as unicode string
    """
    if not arr or len(arr) < 2:
        return ''

    seps = '/\\'

    if ign_case is None:
        ign_case = is_windows()

    def _strip(x):
        if isinstance(x, str):
            return str.strip(x)
        return str.strip(x)

    def _format(v):
        while v and v[-1] in seps:
            v = v[:-1]
        return v
    m = list(filter(_strip, arr))
    s = min(arr, key=len)
    n = len(s)
    si = 0

    for i, c in enumerate(s):
        c_sep = c in seps
        a_sep = c_sep

        for sx in m:
            if sx is s:
                continue

            cx = sx[i]
            cx_sep = cx in seps
            a_sep = a_sep and cx_sep

            if c != cx and not (cx_sep and c_sep):
                if ign_case:
                    if c.lower() != cx.lower():
                        return _format(s[:si])
                else:
                    return _format(s[:si])
        if a_sep:
            si = i + 1

    m.remove(s)
    while m:
        _s = min(m, key=len)
        if _s and len(_s) > n:
            for _ms in m:
                if _ms[n] not in seps:
                    return _format(s[:si])
        m.remove(_s)
    return _format(s)


def find_file_with_ext(directory, extensions) -> str:
    """ Return first file with one of the given extension from directory.
    :param directory: name of the directory
    :param list extensions: list of acceptable extensions (with dot,
                            ie. ".png", ".txt")
    :return str: name of the first file wich extension is in
    """
    extensions = [y.lower() for y in extensions]
    for root, dirs, files in os.walk(directory):
        for name in files:
            _, ext = os.path.splitext(name)
            if ext.lower() in extensions:
                return os.path.join(root, name)
    raise RuntimeError('Not found')


def outer_dir_path(path):
    upper_dir = os.path.dirname(os.path.dirname(path))
    file_name = os.path.basename(path)
    return os.path.join(upper_dir, file_name)


def inner_dir_path(path, directory):
    current_dir = os.path.dirname(path)
    filename = os.path.basename(path)
    return os.path.join(current_dir, directory, filename)


def has_ext(filename, ext, case_sensitive=False):
    if case_sensitive:
        return filename.endswith(ext)
    return filename.lower().endswith(ext.lower())


def free_partition_space(directory):
    """Returns free partition space. The partition is determined by the
       given directory.
    :param directory: Directory to determine partition by
    :return: Free space in kB
    """
    if is_windows():
        free_bytes = ctypes.c_ulonglong(0)
        ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(directory),
                                                   None, None,
                                                   ctypes.pointer(free_bytes))
        return free_bytes.value / 1024
    else:
        statvfs = os.statvfs(directory)
        return statvfs.f_bavail * statvfs.f_frsize / 1024


def du(path):
    """Imitates bash "du -sh <path>" command behaviour. Returns the estimated
       size of this directory
    :param str path: path to directory which size should be measured
    :return str: directory size in human readable format (eg. 6.5M) or "-1"
                 if an error occurs.
    """
    try:
        logger.debug('du -sh %r', path)
        return subprocess.check_output(['du', '-sh', path]).decode().split()[0]
    except (ValueError, OSError, subprocess.CalledProcessError):
        try:
            size = int(get_dir_size(path))
        except OSError as err:
            logger.info("Can't open dir {}: {}".format(path, str(err)))
            return "-1"

    return memoryhelper.dir_size_to_display(size)


def relative_path(path, prefix):
    if path.startswith(prefix):
        return_path = path.replace(prefix, '', 1)
    else:
        return_path = path

    if prefix:
        while return_path and return_path.startswith(os.path.sep):
            return_path = return_path[len(os.path.sep):]

    return return_path
