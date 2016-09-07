import inspect
import types
from Queue import Queue, Empty

from twisted.internet.defer import Deferred, TimeoutError
from twisted.python.failure import Failure


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
        Iterate over class methods and convert them to commands
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

        assert inspect.isclass(cls)
        CommandHelper.init_interface(cls,
                                     name=name or cls.__name__.lower(),
                                     parent=parent, **kwargs)
        update_methods(cls)

        if parent:
            CommandHelper.add_child(cls, parent)
        elif cls not in CommandStorage.roots:
            CommandStorage.roots.append(cls)
        return cls

    return decorate


def command(name=None, **kwargs):
    """
    Stand-alone command function decorator
    :param name: Command name
    :param parent: Parent command object
    :param kwargs: Additional parameters (see CommandHelper.init_interface)
    :return: decorated function
    """

    def wrapper(func):
        kwargs['parent'] = None

        CommandHelper.set_wrapped(func, w)
        CommandHelper.init_interface(func,
                                     name=name or func.__name__.lower(),
                                     **kwargs)
        if func not in CommandStorage.roots:
            CommandStorage.roots.append(func)
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


def argument(*args, **kwargs):
    """
    Add an argument to command
    :param args: Forwarded positional arguments
    :param kwargs: Forwarded keyword arguments
    :return: decorated function
    """

    def wrapper(func):
        CommandHelper.set_wrapped(func, w)
        CommandHelper.add_argument(func, *args, **kwargs)
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


def identifier(name, optional=False, creates=False, updates=False, deletes=False):
    """
    Add an identifier argument passed to command. Accepts modifiers.
    :param optional: Default to None if not provided
    :param name: Identifier name (must match func. arg name)
    :param creates: Purpose modifier
    :param updates: Purpose modifier
    :param deletes: Purpose modifier
    :return: decorated function
    """

    def wrapper(func):
        kwargs = dict(help='object identifier')
        if optional:
            kwargs['default'] = None

        CommandHelper.set_wrapped(func, w)
        CommandHelper.add_argument(func, name, **kwargs)
        return func

    w = CommandHelper.set_wrapper(wrapper)
    return wrapper


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


class CommandGroup(object):
    client = None
    instance = None

    def __init__(self, client=None):
        self.instance = self.instance or self
        self.client = self.client or client


class CommandHelper(object):

    COMMAND_INTERFACE = '__golem_cmd__'
    WRAPPER_INTERFACE = '__golem_wrp__'

    class Wrapper(object):
        def __init__(self, source=None):
            self.source = source

    @classmethod
    def init_interface(cls, elem, name=None, parent=None, children=None, arguments=None, **kwargs):

        interface = cls.get_interface(elem)

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
    def add_child(cls, elem, parent):
        cls.init_interface(parent)

        children = cls.get_children(parent)
        elem_name = cls.get_name(elem)
        not_exists = elem_name not in children

        if not_exists:
            children[elem_name] = elem
        return not_exists

    @classmethod
    def add_argument(cls, elem, *args, **kwargs):
        cls.init_interface(elem)

        arguments = cls.get_arguments(elem)
        arguments.append(cls.simplify_argument(*args, **kwargs))

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

        arguments = [cls.simplify_argument(a) for a in arguments]

        if interface['arguments']:
            interface['arguments'].extend(arguments)
        else:
            interface['arguments'] = arguments

    @staticmethod
    def simplify_argument(*args, **kwargs):
        if 'action' not in kwargs:
            default = args and args[0].startswith('-')
            boolean = kwargs.pop('boolean', default)

            if boolean:
                kwargs['action'] = 'store_true'
            else:
                kwargs['action'] = 'store'

        if 'default' in kwargs:
            kwargs['nargs'] = '?'

        return args or [], kwargs or {}

    @staticmethod
    def wait_for(deferred, timeout=None):

        if not isinstance(deferred, Deferred):
            return deferred

        queue = Queue()
        deferred.addBoth(queue.put)

        try:
            result = queue.get(True, timeout)
        except Empty:
            raise TimeoutError("Command timed out")

        if isinstance(result, Failure):
            result.raiseException()
        return result

    @staticmethod
    def is_callable(elem):
        return isinstance(elem, types.FunctionType)  # or hasattr(elem, '__call__')

    @staticmethod
    def _public_method(entry):
        return inspect.ismethod(entry) and not entry.__name__.startswith('_')

    @classmethod
    def debug(cls, elem, level=0):
        print("{}{} : {}".format("  " * level if level else "", cls.get_name(elem), elem))
        for c in cls.get_children(elem).values():
            cls.debug(c, level + 1)


class CommandStorage(object):
    roots = []

    @classmethod
    def debug(cls):
        for root in cls.roots:
            CommandHelper.debug(root)
