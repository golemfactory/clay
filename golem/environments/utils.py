import os


def find_program(program):
    """Tries to localize the executable for the requested program.

    :returns: The path to the executable or None if not found.

    Implementation based on
    http://stackoverflow.com/q/377017/test-if-executable-exists-in-python
    """
    def isexe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    # Handle full paths first
    fpath, fname = os.path.split(program)
    if fpath:
        return program if isexe(program) else None

    for path in os.environ.get("PATH").split(os.pathsep):
        path = path.strip('"')
        exe_file = os.path.join(path, program)
        if isexe(exe_file):
            return exe_file
        else:
            exts = os.environ.get("PATHEXT")
            if exts:
                exts = exts.split(os.pathsep)
                for ext in exts:
                    exe_file_ext = exe_file + ext
                    if isexe(exe_file_ext):
                        return exe_file_ext
    return None
