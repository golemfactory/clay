#!/usr/bin/env python
# -*- coding: utf-8 -*-

import copy
import netifaces
import os
import pprint
import re
import shlex
import subprocess
import sys
import time
import traceback
from abc import ABCMeta, abstractmethod

import concurrent.futures

DETACHED_PROCESS = 0x00000008


class Environment(object):
    """
        Stores information on execution environment.
    """

    def __init__(self, args):
        self.args = args
        self.script = args[0]
        self.file = args[1] if len(args) > 1 else None
        self.path = self.get_file_path(self.script)

    def get_file_path(self, file_name):
        pathname = os.path.dirname(file_name)
        return os.path.abspath(pathname)

    def get_dir(self, file_name):
        if file_name.find(os.sep) != -1:
            return file_name.rsplit(os.sep, 1)[0]
        return None

    def full_from_relative_path(self, file_name):
        tmp = file_name.strip()

        if tmp.startswith(os.sep):
            return tmp
        return os.path.join(self.path, tmp)

# context


class ContextEntryType(object):
    """Value type with validation"""

    _regex = None

    def __init__(self, regex=None):
        if regex:
            self._regex = re.compile(regex)

    def validate(self, key, value):
        if self._regex and not self._regex.match(value):
            raise ValueError("Invalid value {}".format(value))


class StringContextEntry(ContextEntryType):

    def __init__(self, regex=None):
        super(StringContextEntry, self).__init__(regex)

    def validate(self, key, value):
        if not isinstance(value, basestring):
            raise ValueError("String expected for {}".format(key))

        super(StringContextEntry, self).validate(key, value)


class NumberContextEntry(ContextEntryType):

    def __init__(self):
        super(NumberContextEntry, self).__init__(
            "^[\-]?[1-9][0-9]*\.?[0-9]+$")

    def validate(self, key, value):
        super(NumberContextEntry, self).validate(key, value)


class IntegerContextEntry(NumberContextEntry):
    def __init__(self, constrained=None):
        super(IntegerContextEntry, self).__init__()
        self._regex = "^[\-][1-9]+[0-9]*|[0-9]+$"
        self.constrained = constrained

    def validate(self, key, value):
        converted = None
        try:
            converted = int(value)
        except:
            raise ValueError("Integer expected for {}".format(key))

        if self.constrained is not None and converted != self.constrained:
            raise ValueError("Expected value {} for {}"
                             .format(self.constrained, key))

        super(IntegerContextEntry, self).validate(key, value)


class ArrayContextEntry(ContextEntryType):

    _value_type = None

    def __init__(self, value_type):
        super(ArrayContextEntry, self).__init__()
        self._value_type = value_type

    def validate(self, key, value):
        super(ArrayContextEntry, self).validate(key, value)

        if not isinstance(value, list):
            raise ValueError("Value must be an array")

        if self._value_type:
            for entry in value:
                if not isinstance(entry, self._value_type):
                    raise ValueError(
                        "Invalid value of type {}".format(
                            type(value).__name__))


class DictContextEntry(ContextEntryType):

    _value_type = None

    def __init__(self, value_type):
        super(DictContextEntry, self).__init__()
        self._value_type = value_type

    def validate(self, key, value):
        super(DictContextEntry, self).validate(key, value)

        if not isinstance(value, dict):
            raise ValueError("Value must be a dictionary")

        if self._value_type:
            for entry in value:
                if not isinstance(entry, self._value_type):
                    raise ValueError(
                        "Invalid value of type {}".format(
                            type(value).__name__))


class OrContextEntry(ContextEntryType):

    _entries = None

    def __init__(self, *entries):
        super(OrContextEntry, self).__init__()
        self._entries = entries

    def validate(self, key, value):

        result = False

        for arg in self._entries:
            try:
                arg.validate(key, value)
            except Exception as ex:
                print "Error occurred during arguments validation: {}".format(ex)
            else:
                result = True
                break

        if not result:
            raise ValueError("Invalid value of type {}".format(
                             type(value).__name__))


class AndContextEntry(ContextEntryType):

    _entries = None

    def __init__(self, *entries):
        super(AndContextEntry, self).__init__()
        self._entries = entries

    def validate(self, key, value):
        for arg in self._entries:
            arg.validate(key, value)


class AutoContextEntry(ContextEntryType):

    _type = None

    def __init__(self, value):
        self._type = type(value)

    def validate(self, key, value):
        if self._type is not type(value):
            raise ValueError("Invalid value of type {}".format(
                             type(value).__name__))


class ContextValidator(object):
    """Common context validation"""

    def __init__(self, required_entries):
        self._required_entries = required_entries

    def validate(self, context):
        if not context:
            raise ValueError("Execution context was not provided")

        required = copy.copy(self._required_entries)

        if required:
            for key, value in context.iteritems():
                if key in required:
                    del required[key]

        if required:
            raise ValueError("Missing context entries: %r" % required)

# commands


class CommandException(Exception):
    def __init__(self, message, errors=None):
        super(CommandException, self).__init__(message)
        self.errors = errors


class NodeExecException(Exception):
    def __init__(self, message, errors=None):
        super(NodeExecException, self).__init__(message)
        self.errors = errors


class ExitException(Exception):
    def __init__(self, message=None):
        super(ExitException, self).__init__(message)


class ParamConstraints(object):
    def __init__(self, min_len, constraints):
        self.min_len = min_len
        self.constraints = constraints


class ParamValidator(object):
    """Command parameters validation"""

    def __init__(self, constraints):
        self._constraints = constraints

    def validate(self, context):
        constraints = self._constraints
        cmd = context.get('cmd')

        if constraints:
            min_len = constraints.min_len
            cmd_len = len(cmd)

            if cmd_len < min_len:
                raise CommandException('Insufficient parameters')

            for key, value in constraints.constraints.iteritems():
                if key >= cmd_len:
                    raise CommandException('Invalid command param constraints')
                try:
                    value.validate(key, cmd[key])
                except Exception as e:
                    raise CommandException(e.message)


class Command(object):
    """Simulator command abstraction"""

    __metaclass__ = ABCMeta

    def __init__(self, name, desc,
                 context_constraints=None, cmd_constraints=None):

        self.name = name
        self.desc = desc.format(name=name)

        self._context_validator = ContextValidator(context_constraints)
        self._param_validator = ParamValidator(cmd_constraints)

    @abstractmethod
    def execute(self, context):
        self._context_validator.validate(context)
        self._param_validator.validate(context)


class NodeNameValidatorMixin(object):

    def _extract_nodes(self, node_str):
        if node_str == '*':
            return (True, None, None)
        elif node_str.startswith('~'):
            return (False, True, node_str[1:].split(','))
        return (False, False, node_str.split(','))

    def _valid_node(self, node, nodes, negated=False):

        result = False

        for n in nodes:
            if node.startswith(n):
                result = True
                break

        return not result if negated else result


def node_submit_command(node, commands, detached=False):

    print "Node [%r]: %r" % (node, ' '.join(commands))

    if detached:
        args = ["himage", '-b', node]
    else:
        args = ["himage", node]

    if isinstance(commands, basestring):
        args = args + [commands]
    else:
        args.extend(commands)

    return subprocess.check_output(args)


class NodeCommand(Command, NodeNameValidatorMixin):
    """Command to execute on a target node"""

    def __init__(self, name, detached=False):

        context_required = {
            "nodes": ArrayContextEntry(StringContextEntry),
            "state": AutoContextEntry(SimulatorState.started)
        }

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        desc = """Execute a command on target node.
            {name} [node] [command]
        """

        self.detached = detached

        super(NodeCommand, self).__init__(name, desc,
                                          context_required,
                                          cmd_required)

    def execute(self, context):

        super(NodeCommand, self).execute(context)

        cmd = context.get('cmd')
        capture = context.get('capture')
        capture_data = context.get('capture_data')
        nodes = context.get('nodes')

        _any, _neg, _nodes = self._extract_nodes(cmd[0])
        node_cmd = cmd[1:]

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:

            futures = {executor.submit(node_submit_command, name, node_cmd,
                                       self.detached):
                       name for name in nodes
                       if _any or self._valid_node(name, _nodes, _neg)}

            if not futures:
                raise CommandException('Invalid nodes {}'.format(_nodes))

            for future in concurrent.futures.as_completed(futures):
                try:

                    result = future.result()
                    if capture:
                        capture_data.append(result[:-1])

                except subprocess.CalledProcessError as e:
                    print ':: Node error:', e.returncode, e.output
                    raise NodeExecException(e.message)


class NodeCaptureOutputCommand(Command):

    def __init__(self):

        desc = """Capture nodes' stdout.
            {name}
        """

        super(NodeCaptureOutputCommand, self).__init__("capture", desc)

    def execute(self, context):

        super(NodeCaptureOutputCommand, self).execute(context)

        context_update = {
            'capture': True,
            'capture_data': []
        }

        return context_update


class NodeDumpOutputCommand(Command):

    def __init__(self):

        cmd_required = ParamConstraints(1, {
                                        0: StringContextEntry()
                                        })

        desc = """Dump node's stdout since last capture command
            {name} [output_file]
        """

        super(NodeDumpOutputCommand, self).__init__("dump", desc,
                                                    None,
                                                    cmd_required)

    def execute(self, context):

        super(NodeDumpOutputCommand, self).execute(context)

        environment = context.get('environment')
        cmd = context.get('cmd')
        data = context.get('capture_data')
        target_file = environment.full_from_relative_path(cmd[0])

        try:
            with open(target_file, 'w+') as out:
                for line in data:
                    out.write(line)
        except:
            traceback.print_exc()
            raise CommandException('Cannot write to {}'.format(target_file))

        context_update = {
            'capture': False,
            'capture_data': []
        }

        return context_update


def parse_ifconfig_output(output, iface=None):
    addr_line_found = False

    for line in output.split("\n"):

        if addr_line_found:
            prefix = "inet addr:"
            i = line.index(prefix)
            j = i + len(prefix)
            k = line.index(" ", j)
            return line[j:k]

        # skip to the first interface other than 'lo' or 'ext0'
        if line == "" or line.startswith(" "):
            continue

        intf_name = line.split(" ", 1)[0]
        if intf_name != "lo" and intf_name != "ext0" and not iface \
                or iface and intf_name.startswith(iface):

            addr_line_found = True

    return None


class NodeIpAddrCommand(Command, NodeNameValidatorMixin):

    def __init__(self):

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        desc = """Export node's ip addr to an env var
            {name} [node] [var_name]
        """

        super(NodeIpAddrCommand, self).__init__("ip-addr", desc,
                                                None,
                                                cmd_required)

    def get_node_address(self, node_name):
        output = subprocess.check_output(["himage", node_name, "ifconfig"])
        return parse_ifconfig_output(output)

    def execute(self, context, n_calls=None):

        super(NodeIpAddrCommand, self).execute(context)

        cmd = context.get('cmd')
        nodes = context.get('nodes')
        variables = context.get('variables')
        variable_name = cmd[1]

        _any, _neg, _nodes = self._extract_nodes(cmd[0])

        for name in nodes:
            if _any or self._valid_node(name, _nodes, _neg):
                value = self.get_node_address(name)

        variables[variable_name] = value or ''


class NodeExportCommand(Command, NodeNameValidatorMixin):

    def __init__(self):

        cmd_required = ParamConstraints(3, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry(),
                                        2: StringContextEntry()
                                        })

        desc = """Export node cmd execution output to a variable
            {name} [node] [var_name] [cmd]
        """

        super(NodeExportCommand, self).__init__("node-export", desc,
                                                None,
                                                cmd_required)

    def execute(self, context, n_calls=None):

        super(NodeExportCommand, self).execute(context)

        cmd = context.get('cmd')
        nodes = context.get('nodes')
        variables = context.get('variables')

        _any, _neg, _nodes = self._extract_nodes(cmd[0])
        variable_name = cmd[1]
        node_cmd = cmd[2:]

        result = ''

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:

            futures = {executor.submit(node_submit_command, name, node_cmd, False):
                       name for name in nodes
                       if _any or self._valid_node(name, _nodes, _neg)}

            if not futures:
                raise CommandException('Invalid nodes {}'.format(_nodes))

            for future in concurrent.futures.as_completed(futures):
                try:
                    result += future.result()
                except subprocess.CalledProcessError as e:
                    print ':: Node error:', e.returncode, e.output
                    raise NodeExecException(e.message)

        variables[variable_name] = result.strip().rstrip("\n") or ''


class NodeNatCommand(Command, NodeNameValidatorMixin):

    iptables_nat_cmds = ["iptables --policy FORWARD DROP".split(),
        "iptables -t nat -A POSTROUTING -o {{if1}} -j MASQUERADE".split(),
        "iptables -A FORWARD -i {{if1}} -o {{if2}} -m state"
        " --state RELATED,ESTABLISHED -j ACCEPT".split(),
        "iptables -A FORWARD -i {{if2}} -o {{if1}} -j ACCEPT".split()]

    def __init__(self):

        cmd_required = ParamConstraints(1, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry(),
                                        2: StringContextEntry()
                                        })

        desc = """Configure (iptables) NAT on node
            {name} [node]
        """

        super(NodeNatCommand, self).__init__("nat", desc,
                                             None,
                                             cmd_required)

    def execute(self, context, n_calls=None):

        super(NodeNatCommand, self).execute(context)

        cmd = context.get('cmd')
        nodes = context.get('nodes')
        if1 = cmd[1]
        if2 = cmd[2]

        _any, _neg, _nodes = self._extract_nodes(cmd[0])

        nat_cmd = copy.copy(self.iptables_nat_cmds)

        for line in nat_cmd:
            for i, sub_line in enumerate(line):
                if sub_line == '{{if1}}':
                    line[i] = if1
                elif sub_line == '{{if2}}':
                    line[i] = if2

        for name in nodes:
            if _any or self._valid_node(name, _nodes, _neg):
                for line in nat_cmd:
                    subprocess.check_call(["himage", name] + line)


class NodeCopyCommand(Command, NodeNameValidatorMixin):

    def __init__(self):

        context_required = {
            "nodes": ArrayContextEntry(StringContextEntry),
            "state": AutoContextEntry(SimulatorState.started)
        }

        cmd_required = ParamConstraints(3, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry(),
                                        2: StringContextEntry()
                                        })

        desc = """Copy a local file.
            {name} [node] [local_file] [container_path]
        """

        super(NodeCopyCommand, self).__init__("copy", desc,
                                              context_required,
                                              cmd_required)

    def execute(self, context, n_calls=None):

        super(NodeCopyCommand, self).execute(context)

        environment = context.get('environment')
        cmd = context.get('cmd')
        nodes = context.get('nodes')

        _any, _neg, _nodes = self._extract_nodes(cmd[0])

        src_file = environment.full_from_relative_path(cmd[1])
        target_file = cmd[2]

        for name in nodes:
            if _any or self._valid_node(name, _nodes, _neg):

                docker_name = subprocess.check_output(['himage', '-v',
                                                      name]).strip("\n")

                subprocess.check_output(["docker", "cp", src_file,
                                        docker_name + ":" + target_file],
                                        stderr=subprocess.STDOUT)


class SimulatorState(object):
    idle = 1
    started = 2
    stopped = 3


class SimulatorCommand(Command):
    """Simulator command abstraction"""

    __metaclass__ = ABCMeta

    def __init__(self, name, usage,
                 context_constraints=None, cmd_constraints=None):
        super(SimulatorCommand, self).__init__(name, usage,
                                               context_constraints,
                                               cmd_constraints)


class SimulatorStartCommand(SimulatorCommand):

    _nodes_regex_postfix = '[ \t\r\n]+\((.*[^\)])\)'
    _nodes_regex = None

    def __init__(self):

        context_required = {
            "state": OrContextEntry(
                AutoContextEntry(SimulatorState.started),
                AutoContextEntry(SimulatorState.idle)
            )
        }

        cmd_required = ParamConstraints(1,
                                        {0: StringContextEntry("^.*\.imn$")})

        desc = """Start IMUNES simulator with a specified network.
            {name} [network_file]
        """

        super(SimulatorStartCommand, self).__init__("start", desc,
                                                    context_required,
                                                    cmd_required)

    def execute(self, context):
        super(SimulatorStartCommand, self).execute(context)

        experiment = context.get('experiment')
        environment = context.get('environment')
        network_file = environment.full_from_relative_path(context.get('cmd')[0])

        if not self._nodes_regex:
            self._nodes_regex = re.compile(experiment + self._nodes_regex_postfix)

        subprocess.check_call(["imunes", "-e", experiment, "-b", network_file])

        time.sleep(2)

        output = subprocess.check_output(["himage", "-l"])
        matches = self._nodes_regex.search(output).groups()
        nodes = []

        if matches:
            nodes = matches[0].replace('\n', '').split()

        node_map = {}
        for node in nodes:
            try:
                sim_name = subprocess.check_output(["himage", "-v", node])
                node_map[node] = sim_name.replace("\n", '').strip()
            except Exception as ex:
                print "Subprocess error: {}".format(ex)

        context_update = {
            'state': SimulatorState.started,
            'experiment': experiment,
            'network': network_file,
            'nodes': nodes,
            'node_map': node_map
        }

        return context_update


class SimulatorStopCommand(SimulatorCommand):

    def __init__(self):

        context_required = {
            "state": IntegerContextEntry(SimulatorState.started)
        }

        desc = """Stop IMUNES.
            {name} ([experiment])
        """

        super(SimulatorStopCommand, self).__init__("stop", desc,
                                                   context_required)

    def execute(self, context):

        cmd = context.get('cmd')
        sim_experiment = context.get('experiment')
        experiment = cmd[0] if cmd and len(cmd) else sim_experiment

        subprocess.check_call(["imunes", "-b", "-e",
                               experiment])

        time.sleep(2)

        if experiment is sim_experiment:

            context_update = {
                'state': SimulatorState.stopped,
                'network': None,
                'nodes': []
            }

            return context_update

        return None


class SimulatorSleepCommand(SimulatorCommand):

    def __init__(self):

        desc = """Sleep for n seconds.
            {name} [n]
        """

        cmd_required = ParamConstraints(1,
                                        {0: IntegerContextEntry()})

        super(SimulatorSleepCommand, self).__init__("sleep", desc, None,
                                                    cmd_required)

    def execute(self, context):
        secs = int(context.get('cmd')[0])
        time.sleep(secs)


class SimulatorExitCommand(SimulatorCommand):

    def __init__(self):
        super(SimulatorExitCommand, self).__init__("exit", "")

    def execute(self, context):
        raise ExitException()


class SimulatorHelpCommand(SimulatorCommand):

    def __init__(self):
        super(SimulatorHelpCommand, self).__init__("help", "([command])")

    def execute(self, context):

        commands = context.get('commands')
        cmd = context.get('cmd')

        if cmd:
            help_for = cmd[0]
            if help_for is not self.name and help_for in commands:
                print commands.get(help_for).desc
                return

        print commands.keys()


class SimulatorPrintCommand(SimulatorCommand):

    def __init__(self):

        desc = """Print a string.
            {name} [string]
        """

        super(SimulatorCommand, self).__init__("print", desc)

    def execute(self, context):

        cmd = context.get('cmd')
        capture = context.get('capture')
        capture_data = context.get('capture_data')
        data = ''

        if cmd:
            data = ' '.join(cmd)
        if capture:
            capture_data.append(data)

        print data


class SimulatorEnvCommand(SimulatorCommand):

    def __init__(self):

        desc = """Print env data.
            {name} [env_entry]
        """

        cmd_required = ParamConstraints(1, {0: StringContextEntry()})

        super(SimulatorEnvCommand, self).__init__("env", desc,
                                                  None, cmd_required)

    def execute(self, context):
        cmd = context.get('cmd')

        if cmd:
            print context.get(cmd[0])
        else:
            print "None"


class SimulatorLocalCommand(SimulatorCommand):

    def __init__(self, name, detached=False):

        desc = """Run command locally.
            {name} [command(s)]
        """

        cmd_required = ParamConstraints(1, {0: StringContextEntry()})

        self.detached = detached

        super(SimulatorLocalCommand, self).__init__(name, desc,
                                                    None, cmd_required)

    def execute(self, context):

        cmd = context.get('cmd')
        if self.detached:
            subprocess.Popen(cmd[0:],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             stdin=subprocess.PIPE)
        else:
            output = subprocess.check_output(cmd)
            print output,


class SimulatorExperimentCommand(SimulatorCommand):

    def __init__(self):

        desc = """Set or get experiment name.
            {name} ([name])
        """

        super(SimulatorExperimentCommand, self).__init__("experiment",
                                                         desc)

    def execute(self, context):

        cmd = context.get('cmd')
        state = context.get('state')
        experiment = context.get('experiment')

        if cmd:
            context_update = {'experiment': cmd[0]}
            return state, context_update

        print experiment


class SimulatorExportCommand(SimulatorCommand):

    def __init__(self):

        desc = """Set an env variable as a result of local command.
            {name} [var] [command(s)]
        """

        cmd_required = ParamConstraints(2, {0: StringContextEntry()})

        super(SimulatorExportCommand, self).__init__("export", desc,
                                                     None, cmd_required)

    def execute(self, context):

        cmd = context.get('cmd')
        var = cmd[0]
        params = cmd[1:]
        output = subprocess.check_output(params)

        variables = context.get('variables')
        # skip the newline char
        variables[var] = output[:-1] if output else ''


class SimulatorInterfacesCommand(Command):

    def __init__(self):

        cmd_required = ParamConstraints(1, {
                                        0: StringContextEntry()
                                        })

        desc = """Export local interfaces to an env var
            {name} [var_name]
        """

        super(SimulatorInterfacesCommand, self).__init__("ifaces", desc,
                                                         None,
                                                         cmd_required)

    def execute(self, context, n_calls=None):

        super(SimulatorInterfacesCommand, self).execute(context)

        variables = context.get('variables')
        cmd = context.get('cmd')
        variable = cmd[0]

        interfaces = netifaces.interfaces()

        if "lo" in interfaces:
            interfaces.remove("lo")

        variables[variable] = interfaces


class SimulatorNodesCommand(Command):

    def __init__(self):

        cmd_required = ParamConstraints(1, {
                                        0: StringContextEntry()
                                        })

        desc = """Export imunes' nodes to an env var
            {name} [var_name]
        """

        super(SimulatorNodesCommand, self).__init__("nodes", desc,
                                                    None, cmd_required)

    def execute(self, context, n_calls=None):

        super(SimulatorNodesCommand, self).execute(context)

        variables = context.get('variables')
        nodes = context.get('nodes')
        cmd = context.get('cmd')
        variable = cmd[0]
        variables[variable] = [n for n in nodes if not n.startswith('switch')]


class SimulatorNodeMapCommand(Command):

    def __init__(self):

        cmd_required = ParamConstraints(1, {
                                        0: StringContextEntry()
                                        })

        desc = """Export node mapping to an env var
            {name} [var_name]
        """

        super(SimulatorNodeMapCommand, self).__init__("node-map", desc,
                                                      None,
                                                      cmd_required)

    def execute(self, context, n_calls=None):

        super(SimulatorNodeMapCommand, self).execute(context)

        variables = context.get('variables')
        node_map = context.get('node_map')
        cmd = context.get('cmd')
        variable = cmd[0]
        variables[variable] = node_map


class SimulatorForEachCommand(Command):

    def __init__(self):

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        desc = """ForEach loop start
            {name} [var_name] [element_name]
        """

        super(SimulatorForEachCommand, self).__init__("for", desc,
                                                      None,
                                                      cmd_required)

    def execute(self, context, n_calls=None):

        super(SimulatorForEachCommand, self).execute(context)

        loop_stack = context.get('loop_stack')
        variables = context.get('variables')
        cmd = context.get('cmd')

        source = variables.get(cmd[0], [])
        var = cmd[1]

        loop = {
            'source': source,
            'source_idx': -1,
            'source_len': len(source),
            'var': var,
            'value': variables.get(var, None),
            'commands': [],
            'command_idx': 0,
            'command_len': 0,
            'record': True
        }

        loop_stack.append(loop)


class SimulatorEndForEachCommand(Command):

    def __init__(self):
        desc = """ForEach loop end
            {name}
        """

        super(SimulatorEndForEachCommand, self).__init__("endfor", desc,
                                                         None)

    def execute(self, context):
        loop_stack = context.get('loop_stack')
        loop = loop_stack[-1] if loop_stack else None

        if loop:
            commands = loop['commands']
            loop['record'] = False
            if commands:
                loop['commands'] = commands[:-1]
                loop['command_len'] = len(loop['commands'])


class SimulatorEvalCommand(Command):

    def __init__(self):
        desc = """Eval command and store the result in a variable
            {name} [variable] [code]
        """

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        super(SimulatorEvalCommand, self).__init__("eval", desc,
                                                   None,
                                                   cmd_required)

    def execute(self, context):

        super(SimulatorEvalCommand, self).execute(context)

        cmd = context.get('cmd')
        var = cmd[0]
        variables = context.get('variables')
        variables[var] = eval(' '.join(cmd[1:]))


class SimulatorLetCommand(Command):

    def __init__(self):
        desc = """Store the value in a variable
            {name} [variable] [value]
        """

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        super(SimulatorLetCommand, self).__init__("let", desc,
                                                  None,
                                                  cmd_required)

    def execute(self, context):

        super(SimulatorLetCommand, self).execute(context)

        cmd = context.get('cmd')
        var = cmd[0]
        variables = context.get('variables')
        variables[var] = ' '.join(cmd[1:])


class SimulatorExecFileCommand(Command):

    def __init__(self):
        desc = """Eval command and store the result in a variable
            {name} [variable] [file]
        """

        cmd_required = ParamConstraints(2, {
                                        0: StringContextEntry(),
                                        1: StringContextEntry()
                                        })

        super(SimulatorExecFileCommand, self).__init__("execfile", desc,
                                                       None,
                                                       cmd_required)

    def execute(self, context):

        super(SimulatorExecFileCommand, self).execute(context)

        cmd = context.get('cmd')
        var = cmd[0]
        variables = context.get('variables')
        variables[var] = execfile(cmd[1])


class Simulator(object):
    """
        Main project class. Reads commands from stdin and executes
        them on target IMUNES nodes.
    """

    experiment = "SIM"
    commands = {}
    nodes = {}

    _var_regex = re.compile("\%\{[^\}]*\}")

    def __init__(self, environment):
        self.environment = environment

        self.__add_command(SimulatorStartCommand())
        self.__add_command(SimulatorStopCommand())
        self.__add_command(SimulatorSleepCommand())
        self.__add_command(SimulatorHelpCommand())
        self.__add_command(SimulatorEnvCommand())
        self.__add_command(SimulatorLocalCommand("local"))
        self.__add_command(SimulatorLocalCommand("local-d", detached=True))
        self.__add_command(SimulatorInterfacesCommand())
        self.__add_command(SimulatorNodesCommand())
        self.__add_command(SimulatorNodeMapCommand())
        self.__add_command(SimulatorExportCommand())
        self.__add_command(SimulatorEvalCommand())
        self.__add_command(SimulatorLetCommand())
        self.__add_command(SimulatorExecFileCommand())
        self.__add_command(SimulatorExperimentCommand())
        self.__add_command(SimulatorForEachCommand())
        self.__add_command(SimulatorEndForEachCommand())
        self.__add_command(SimulatorPrintCommand())
        self.__add_command(SimulatorExitCommand())

        self.__add_command(NodeCommand("node"))
        self.__add_command(NodeCommand("node-d", detached=True))
        self.__add_command(NodeCopyCommand())
        self.__add_command(NodeCaptureOutputCommand())
        self.__add_command(NodeDumpOutputCommand())
        self.__add_command(NodeIpAddrCommand())
        self.__add_command(NodeExportCommand())
        self.__add_command(NodeNatCommand())

    def start(self):

        context = {
            'experiment': self.experiment,
            'nodes': self.nodes,
            'commands': self.commands,
            'environment': self.environment,
            'state': SimulatorState.idle,
            'variables': {},
            'capture': False,
            'capture_data': [],
            'loop_stack': []
        }

        source = sys.stdin
        if self.environment.file:
            source = open(self.environment.file)

        try:
            self._start(source, context)
        except ExitException:
            pass
        except:
            raise

        if self.environment.file:
            source.close()

    def _start(self, source, context):

        working = True
        while working:

            loop = context['loop_stack'][-1] if context['loop_stack'] else None

            if loop:
                line = self._process_loop(source, context, loop)
            else:
                line = self._read_source(source)

            if not line or line.startswith('#'):
                continue

            parsed = shlex.split(line)
            name = parsed[0]
            data = parsed[1:] if len(parsed) > 1 else []

            if name == 'source':

                if not data:
                    print ':: No source file specified'
                else:
                    try:
                        with open(data[0]) as source:
                            self._start(source, context)
                    except Exception as e:
                        print ':: Cannot open file', data[0], e.message

            elif name in self.commands:

                command = self.commands.get(name)
                context['cmd'] = self._set_cmd_vars(context, data)

                print '[dbg]', name, ' '.join(context['cmd'] or [])

                try:
                    result = command.execute(context)
                except ExitException:
                    working = False
                except CommandException as e:
                    print e
                    print command.desc
                except Exception as e:
                    print ':: Error executing command: {}'.format(e)
                    traceback.print_exc()
                    working = False
                else:
                    if result:
                        context.update(result)

            else:
                print ':: Unknown command: {}'.format(name)

        self._cleanup(context)

    def _read_source(self, source):
        line = source.readline()
        if not line:
            raise ExitException()
        return line.strip()

    def _process_loop(self, source, context, loop):

        record = loop['record']
        variables = context['variables']

        if loop['command_idx'] == 0:
            loop['source_idx'] += 1

            if loop['source_idx'] >= loop['source_len']:
                value = loop['value']
                variables[loop['var']] = value
                context['loop_stack'].pop()
                return None

            var = loop['var']
            variables[var] = loop['source'][loop['source_idx']]

        if record:
            line = self._read_source(source)
            loop['commands'].append(line)
        else:
            if loop['command_idx'] >= loop['command_len']:
                loop['command_idx'] = 0
                return None
            line = loop['commands'][loop['command_idx']]
            loop['command_idx'] += 1

        return line

    def _cleanup(self, context):
        if context.get('state') == SimulatorState.started:
            self.commands.get('stop').execute(context)
        sys.stderr.flush()
        sys.stdout.flush()
        sys.stdout = sys.__stdout__

    def __add_command(self, command):
        self.commands[command.name] = command

    def _decorate_var(self, var):
        return '%{' + var + '}'

    def _extract_var_names(self, line):
        found = self._var_regex.findall(line)
        results = []

        if found:
            for match in found:
                result = match.replace('%{', '')
                result = result.replace('}', '')

                results.append(result)

        return results

    def _set_cmd_vars(self, context, data):
        variables = context.get('variables')

        if data:
            data_copy = data[:]

            for i, item in enumerate(data_copy):
                extracted = self._extract_var_names(item)
                data_copy[i] = self._replace_vars(item,
                                                  extracted,
                                                  variables)

            return data_copy
        return None

    def _replace_vars(self, line, extracted, env_variables):
        for e in extracted:
            if e in env_variables:

                value = env_variables.get(e)
                if isinstance(value, dict) or isinstance(value, list):
                    value = pprint.pformat(value)

                decorated = self._decorate_var(e)
                line = line.replace(decorated, unicode(value))
        return line


def main(args):
    environment = Environment(args)
    simulator = Simulator(environment)
    simulator.start()


if __name__ == '__main__':

    if os.geteuid() != 0:
        print "This script must be run as root"
        sys.exit(1)

    main(sys.argv)
