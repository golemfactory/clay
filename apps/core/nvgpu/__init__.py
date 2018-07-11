import subprocess

from golem.core.common import is_linux


def is_supported(*_) -> bool:
    if not is_linux():
        return False

    lspci = subprocess.Popen(['lspci'], stdout=subprocess.PIPE)
    grep = subprocess.Popen(['grep', '-i', 'nvidia'], stdin=lspci.stdout,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    lspci.stdout.close()

    out, err = grep.communicate()
    return out.strip()
