import jsonpickle as json
import unittest

from golem.core.simpleserializer import DictSerializer
from golem.interface.command import CommandResult
from golem.interface.formatters import CommandFormatter, CommandJSONFormatter


class TestFormatters(unittest.TestCase):

    def test_command_formatter(self):
        formatter = CommandFormatter()

        for prettify in [True, False]:
            formatter.prettify = prettify

            assert formatter.format(None) is None
            assert formatter.format('') is None
            assert formatter.format('Some text') == 'Some text'

            if not prettify:
                assert formatter.format(formatter) == DictSerializer.dump(formatter, typed=False)

        table_headers = ['First', 'Second', 'Third']
        table_values = [
            ['value 1', 'value 2', 'value 3'],
            ['value 1', 'value 2', 'value 3'],
            ['value 1', 'value 2', 'value 3'],
        ]

        tabular_result = CommandResult.to_tabular(table_headers, table_values)
        tabular_repr = formatter.format(tabular_result)
        tabular_data_repr = formatter.format(tabular_result.from_tabular())

        assert tabular_repr
        assert tabular_data_repr
        assert tabular_data_repr != tabular_repr

    def test_json_command_formatter(self):
        fmt = CommandJSONFormatter()

        json_str = fmt.format(fmt)

        assert json_str and json.loads(json_str)
        assert fmt.format('') is None
        assert fmt.format('test') == '"test"'

    def test_namespace(self):

        ns_dict = dict()

        fmt = CommandFormatter()
        fmt_json = CommandJSONFormatter()

        assert not fmt.supports(ns_dict)
        assert not fmt_json.supports(ns_dict)

        ns_dict = dict(json=False)

        assert not fmt.supports(ns_dict)
        assert not fmt_json.supports(ns_dict)

        ns_dict = dict(json=True)

        assert not fmt.supports(ns_dict)
        assert fmt_json.supports(ns_dict)

        fmt_json.clear_argument(ns_dict)

        assert 'json' not in ns_dict


