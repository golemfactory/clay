import os


def find_program(program):
    """Tries to localize the executable for the requested program.

    :returns: The path to the executable or None if not found.

    Implemenetation based on
    http://stackoverflow.com/q/377017/test-if-executable-exists-in-python
    """
    def isexe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if isexe(program):
            return program
    else:
        for path in os.environ.get("PATH").split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if isexe(exe_file):
                return exe_file
    return None
