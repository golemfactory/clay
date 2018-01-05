# Authors: Douglas Creager <dcreager@dcreager.net>
#          Calum Lind <calumlind@gmail.com>
#          Dariusz Rybi <jiivanq@gmail.com>
#
# This file is placed into the public domain.
#
# Calculates the current version number by first checking output of
# “git describe”, modified to conform to PEP 386 versioning scheme.
# If “git describe” fails (likely due to using release tarball rather
# than git working copy), then fall back on reading the contents of
# the RELEASE-VERSION file.
#
# Usage: Import in setup.py, and use result of get_version() as package
# version:
#
# from version import get_version
#
# setup(
#     ...
#     version=get_version(),
#     ...
# )
#
# Script will automatically update the RELEASE-VERSION file, if needed.
# Note that  RELEASE-VERSION file should *not* be checked into git; please add
# it to your top-level .gitignore file.
#
# You'll probably want to distribute the RELEASE-VERSION file in your
# sdist tarballs; to do this, just create a MANIFEST.in file that
# contains the following line:
#
#   include RELEASE-VERSION
#

__all__ = ("get_version")

import pathlib
import subprocess
VERSION_FILE = "RELEASE-VERSION"


def call_git_describe(prefix='', cwd='.'):
    cmd = 'git describe --tags --match %s[0-9]*' % prefix
    try:
        version = subprocess.run(
            cmd.split(),
            stdout=subprocess.PIPE,
            check=True,
        ).stdout.decode()
        version = version.strip()[len(prefix):]
        if '-' in version:
            version = '{}+dev{}.{}'.format(*version.split('-'))
        return version
    except Exception:
        return None


def get_version(prefix='', cwd='.'):
    path = pathlib.Path(cwd) / VERSION_FILE
    try:
        with path.open("r") as f:
            release_version = f.read()
    except Exception:
        release_version = None

    version = call_git_describe(prefix, cwd)

    if version is None:
        version = release_version
    if version is None:
        raise ValueError("Cannot find the version number!")

    if version != release_version:
        with path.open("w") as f:
            f.write(version)

    return version


if __name__ == "__main__":
    print(get_version(prefix='v'))
