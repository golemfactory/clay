import os
import sys
import subprocess
import re
import shlex


var_re = re.compile("\%\{[^\}]*\}")


def _extract_var_names(line):
    found = var_re.findall(line)
    results = []

    if found:
        for match in found:
            result = match.replace('%{', '')
            result = result.replace('}', '')
            results.append(result)

    return results


def _decorate_var(e):
    return '%{'+e+'}'


def _replace_vars(line, extracted, container):
    for e in extracted:
        if e:
            value = None

            if e == 'ip':
                value = ip_addr(container)
            elif e == 'container':
                value = container

            if value:
                decorated = _decorate_var(e)
                line = line.replace(decorated, value)

    return line


def _set_cmd_vars(data, container):
    if data:
        for i, item in enumerate(data):
            extracted = _extract_var_names(item)
            data[i] = _replace_vars(item,
                                    extracted,
                                    container)


def ip_addr(container):
    cmd = "inspect --format '{{ .NetworkSettings.IPAddress }}' " + container
    return run(container, shlex.split(cmd), print_output=False).replace('\n',
                                                                        '')


def run(container, argv, print_output=True):

    _set_cmd_vars(argv, container)

    if argv[0] == 'cp':

        dest = argv[-1]
        pos = dest.rfind(os.sep)

        if pos:
            directory = dest[:pos].split(':')[-1]
            run(container, ['exec', container, 'mkdir', '-p', directory])

        cmd = ['docker'] + argv
        output = __execute(container, cmd,
                           print_output=print_output)

    elif argv[0] == 'exec-bg':

        cmd = ['docker', 'exec'] + argv[1:]
        output = __execute(container, cmd,
                           background=True,
                           print_output=print_output)
    else:

        cmd = ['docker'] + argv
        output = __execute(container, cmd,
                           print_output=print_output)

    return output


def __execute(container, cmd, background=False, print_output=True):
    try:

        joined = ' '.join(cmd)
        print container, ':', joined

        if background:
            os.system(joined)
        else:
            output = subprocess.check_output(cmd)

            if output:
                output = output[:-1]
                if print_output:
                    print output

            return output

    except subprocess.CalledProcessError as e:
        print "\tError:", e
    return None


def main(argv):
    if len(argv) < 3:
        print 'Usage:', argv[0], '[image] [command]'
        sys.exit(1)

    image = argv[1]
    output = subprocess.check_output(['docker', 'ps', '-q',
                                     '-f', 'image=%s' % image])
    containers = output.split("\n")

    for container in containers:
        if container:
            run(container, argv[2:])

if __name__ == '__main__':
    main(sys.argv)
