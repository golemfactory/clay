import os
import shutil


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
