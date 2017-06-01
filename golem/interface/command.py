import inspect
import types

from contextlib import contextmanager
from operator import itemgetter

from golem.interface.exceptions import CommandException


def group(name=None, parent=None, **kwargs):
    """
    Command group class decorator
    :param name: Command (and group) name
    :param parent: Parent command object
    :param kwargs: Additional parameters (see CommandHelper.init_interface)
    :return: decorated class
    """

    def update_methods(cls):
        """
        Iterate over non-static methods and convert them to commands
        :param cls: Class to inspect
        :return: None
        """
        for _, method in CommandHelper.get_methods(cls):

            if CommandHelper.is_wrapper(method):
                method = CommandHelper.get_wrapped(method)

            if inspect.ismethod(method):
                target = method.__func__
            else:
                target = method

            if not target:
                continue

            interface = CommandHelper.init_interface(target)

            if not interface['parent']:
                interface['parent'] = cls
                CommandHelper.add_child(target, cls)

    def decorate(cls):

        if not inspect.isclass(cls):
            raise TypeError("'cls' should be class, but is: {}".format(type(cls)))

        CommandHelper.init_instance(cls)
        CommandHelper.init_interface(cls,
                                     name=name or cls.__name__.lower(),
                                     parent=parent, **kwargs)
        update_methods(cls)

        if parent:
            CommandHelper.add_child(cls, parent)
        else:
            CommandHelper.add_root(cls)
        return cls

    return decorate


def command(name=None, root=False, **kwargs):
    """
    Command function decorator
    :param name: Command name
    :param root: Force as root command
    :param parent: Parent command object
    :param kwargs: Additional parameters (see CommandHelper.init_interface)
    :return: decorated function
    """

    def wrapper(func):
        parent = kwargs.get('parent', None)

        CommandHelper.set_wrapped(func, w)
        CommandHelper.init_interface(func,
                                     name=name or func.__name__.lower(),
                                     **kwargs)
        if parent:
            CommandHelper.add_child(func, parent)
        elif root:
            CommandHelper.add_root(func)
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


def argument(*args, **kwargs):
    """
    Add an argument to a command
    :param kwargs: Forwarded keyword arguments
    :return: decorated function
    """

    def wrapper(func):
        CommandHelper.set_wrapped(func, w)
        CommandHelper.add_argument(func, Argument(*args, **kwargs))
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


def identifier(name, **kwargs):
    return argument(name, help=kwargs.pop('help', 'Object id'), **kwargs)


def doc(value):
    """
    Set command's help string (corresponds to argparse's 'help')
    :param value: Documentation contents
    :return: decorated function
    """
    return __property_wrapper_builder('help', value)


def name(value):
    """
    Overrides command's name
    :param value: Name to set
    :return: decorated function
    """
    return __property_wrapper_builder('name', value)


def parent(value):
    """
    Override's command parent group
    :param value: Command object
    :return: decorated function
    """
    return __property_wrapper_builder('parent', value)


def __property_wrapper_builder(prop, value):

    def wrapper(func):
        CommandHelper.set_wrapped(func, w)
        interface = CommandHelper.init_interface(func)
        CommandHelper.update_property(interface, prop, value)
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


class Argument(object):

    def __init__(self, *args, **kwargs):
        self.args = args or list()
        self.kwargs = kwargs or dict()

    def simplify(self):

        args = list(self.args)
        kwargs = dict(self.kwargs)

        is_flag = args and args[0].startswith('-')
        boolean = kwargs.pop('boolean', is_flag)
        optional = kwargs.pop('optional', is_flag)
        default = kwargs.get('default', False if boolean else None)

        if not boolean and optional:
            kwargs['default'] = kwargs.get('default', default)

        if 'action' not in kwargs:
            choices = 'choices' in kwargs

            if boolean and not choices:
                kwargs['action'] = 'store_true'
            else:
                kwargs['action'] = 'store'

        if not boolean and 'default' in kwargs:
            kwargs['nargs'] = '?'

        ret = Argument(*args, **kwargs)
        return ret

    @staticmethod
    def extend(arg, *args, **kwargs):
        new_arg = Argument(*arg.args, **arg.kwargs)
        new_arg.args += args
        new_arg.kwargs.update(kwargs)
        return new_arg


class CommandResult(object):

    NONE = 0
    PLAIN = 1
    TABULAR = 2

    def __init__(self, data=None, type=None, error=None):
        if error:
            raise CommandException(error)

        self.data = data

        if data is None:
            self.type = type or CommandResult.NONE
        else:
            self.type = type or CommandResult.PLAIN

    def from_tabular(self):
        if self.type != CommandResult.TABULAR:
            raise TypeError("Type should be: {}".format(CommandResult.TABULAR))
        data = self.data

        if data and len(data) == 2:
            return data[0], data[1]
        return None, None

    @staticmethod
    def to_tabular(headers, values, sort=None):
        if sort in headers:
            values = CommandResult.sort(headers, values, sort)
        return CommandResult((headers, values), CommandResult.TABULAR)

    @staticmethod
    def sort(headers, values, key):
        if key:
            column_idx = headers.index(key)
            if column_idx != -1:
                values = sorted(values, key=itemgetter(column_idx))
        return values


class CommandHelper(object):

    COMMAND_INTERFACE = '__golem_cmd__'
    WRAPPER_INTERFACE = '__golem_wrp__'

    class Wrapper(object):
        def __init__(self, source=None):
            self.source = source

    @classmethod
    def init_interface(cls, elem, name=None, parent=None, children=None,
                       arguments=None, argument=None, **kwargs):

        interface = cls.get_interface(elem)

        if argument:
            if not arguments:
                arguments = []
            arguments.append(argument)

        if interface:

            cls.update_property(interface, 'name', name)
            cls.update_property(interface, 'parent', parent)
            cls.update_children(interface, children)
            cls.update_arguments(interface, arguments)

            for key, value in kwargs.items():
                cls.update_property(interface, key, value)

        else:

            interface = dict(
                source=elem,
                name=name or elem.__name__.lower(),
                parent=parent,
                callable=cls.is_callable(elem),
                children=children or {},
                arguments=[],
                **kwargs
            )

            cls.update_arguments(interface, arguments)
            cls.set_interface(elem, interface)

        return interface

    @classmethod
    def init_instance(cls, elem):
        instance = elem.__new__(elem)
        setattr(elem, '_cmd_instance', instance)

    @classmethod
    def get_instance(cls, elem):
        if isinstance(elem, types.FunctionType):
            elem = cls.get_parent(elem)
        if elem:
            return getattr(elem, '_cmd_instance')

    @classmethod
    def set_wrapper(cls, elem):
        source = cls.Wrapper()
        setattr(elem, CommandHelper.WRAPPER_INTERFACE, source)
        return source

    @classmethod
    def is_wrapper(cls, elem):
        return hasattr(elem, CommandHelper.WRAPPER_INTERFACE)

    @classmethod
    def get_wrapped(cls, elem):
        w = getattr(elem, CommandHelper.WRAPPER_INTERFACE)
        if w:
            return w.source

    @classmethod
    def set_wrapped(cls, elem, w):
        w.source = elem

    @staticmethod
    def set_interface(elem, interface):
        setattr(elem, CommandHelper.COMMAND_INTERFACE, interface)

    @classmethod
    def get_interface(cls, elem):
        if cls.is_wrapper(elem):
            elem = cls.get_wrapped(elem)
        if hasattr(elem, CommandHelper.COMMAND_INTERFACE):
            return getattr(elem, CommandHelper.COMMAND_INTERFACE)

    @classmethod
    def get_methods(cls, elem):
        return inspect.getmembers(elem, predicate=cls._public_method)

    @classmethod
    def get_name(cls, elem):
        return cls.get_property(elem, 'name')

    @classmethod
    def get_parent(cls, elem):
        return cls.get_property(elem, 'parent')

    @classmethod
    def get_children(cls, elem):
        return cls.get_property(elem, 'children')

    @classmethod
    def get_arguments(cls, elem):
        return cls.get_property(elem, 'arguments')

    @classmethod
    def get_property(cls, elem, prop):
        interface = cls.get_interface(elem)
        if interface:
            return interface.get(prop)

    @classmethod
    def set_property(cls, elem, prop, value):
        interface = cls.get_interface(elem)
        if interface:
            interface.put(prop, value)

    @classmethod
    def add_root(cls, elem):
        not_exists = elem not in CommandStorage.roots
        if not_exists:
            CommandStorage.roots.append(elem)
        return not_exists

    @classmethod
    def add_child(cls, elem, parent):
        cls.init_interface(parent)

        children = cls.get_children(parent)
        elem_name = cls.get_name(elem)
        not_exists = elem_name not in children

        if not_exists:
            children[elem_name] = elem
        return not_exists

    @classmethod
    def add_argument(cls, elem, arg):
        cls.init_interface(elem)

        arguments = cls.get_arguments(elem)
        arguments.append(arg.simplify())

    @classmethod
    def update_property(cls, interface, prop, value):
        if interface and value:
            interface[prop] = value

    @classmethod
    def update_children(cls, interface, children):
        if not (interface and children):
            return

        if interface['children']:
            interface['children'].update(children)
        else:
            interface['children'] = children

    @classmethod
    def update_arguments(cls, interface, arguments):
        if not (interface and arguments):
            return

        arguments = [arg.simplify() for arg in arguments]

        if interface['arguments']:
            interface['arguments'].extend(arguments)
        else:
            interface['arguments'] = arguments

    @classmethod
    def wrap_call(cls, elem, instance=None):
        if not instance:
            instance = cls.get_instance(elem)
        # elem cannot be a static method; they're not parsed by @group
        return lambda *a, **kw: elem(instance, *a, **kw)

    @staticmethod
    def is_callable(elem):
        # or hasattr(elem, '__call__')
        return isinstance(elem, types.FunctionType)

    @staticmethod
    def _public_method(entry):
        return inspect.ismethod(entry) and not entry.__name__.startswith('_')

    @classmethod
    def debug(cls, elem, level=0):
        print("{}{} : {}".format("  " * level if level else "",
                                 cls.get_name(elem), elem))
        for c in cls.get_children(elem).values():
            cls.debug(c, level + 1)


class CommandStorage(object):
    roots = []

    @classmethod
    def debug(cls):
        for root in cls.roots:
            CommandHelper.debug(root)


@contextmanager
def client_ctx(obj, client):

    if hasattr(obj, 'client'):
        previous = getattr(obj, 'client')
    else:
        previous = None

    setattr(obj, 'client', client)
    yield

    if previous:
        setattr(obj, 'client', previous)
    else:
        del obj.client


@contextmanager
def storage_context():
    previous = CommandStorage.roots

    CommandStorage.roots = []
    yield

    CommandStorage.roots = previous
