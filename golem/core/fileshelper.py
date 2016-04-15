import os
import shutil

from golem.core.common import is_windows


def copy_file_tree(src, dst, exclude=None):
    """
    Copy directory and it's content from src to dst. Doesn't copy files with extensions from excluded. Don't remove
    additional files from destination directory.
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


def common_dir(arr, plus_sep=None, ign_case=None):
    """
    Returns a common directory for paths
    :param arr: Array of paths
    :param plus_sep: Extra path separator to include
    :param ign_case: Ignore case in paths
    :return: Common directory prefix as unicode string
    """
    if not arr or len(arr) < 2:
        return ''

    if plus_sep and plus_sep != os.path.sep:
        seps = [os.path.sep, plus_sep]
    else:
        seps = [os.path.sep]

    if os.path.sep != '/':
        seps.append('/')

    if ign_case is None:
        ign_case = is_windows()

    def _strip(x):
        if isinstance(x, unicode):
            return unicode.strip(x)
        return str.strip(x)

    def _format(v):
        while v and v[-1] in seps:
            v = v[:-1]
        return v

    m = filter(_strip, arr[:])
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
            for _s in m:
                if _s[n] not in seps:
                    return _format(s[:si])
        m.remove(_s)
    return _format(s)


def find_file_with_ext(directory, extensions):
    """ Return first file with one of the given extension from directory.
    :param str directory: name of the directory
    :param list extensions: list of acceptable extensions (with dot, ie. ".png", ".txt")
    :return str: name of the first file wich extension is in
    """
    extensions = map(lambda y: y.lower(), extensions)
    for root, dirs, files in os.walk(directory):
        for name in files:
            _, ext = os.path.splitext(name)
            if ext.lower() in extensions:
                return os.path.join(root, name)
