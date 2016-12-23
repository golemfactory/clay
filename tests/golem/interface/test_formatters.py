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

            self.assertIsNone(formatter.format(None))
            self.assertIsNone(formatter.format(''))
            self.assertEqual(formatter.format('Some text'), 'Some text')

            if not prettify:
                self.assertEqual(formatter.format(formatter), DictSerializer.dump(formatter, typed=False))

        table_headers = ['First', 'Second', 'Third']
        table_values = [
            ['value 1', 'value 2', 'value 3'],
            ['value 1', 'value 2', 'value 3'],
            ['value 1', 'value 2', 'value 3'],
        ]

        tabular_result = CommandResult.to_tabular(table_headers, table_values)
        tabular_repr = formatter.format(tabular_result)
        tabular_data_repr = formatter.format(tabular_result.from_tabular())

        self.assertIsNotNone(tabular_repr)
        self.assertIsNotNone(tabular_data_repr)
        self.assertNotEqual(tabular_data_repr, tabular_repr)

    def test_json_command_formatter(self):
        fmt = CommandJSONFormatter()

        json_str = fmt.format(fmt)

        self.assertIsNotNone(json_str)
        self.assertIsNotNone(json.loads(json_str))
        self.assertIsNone(fmt.format(''))
        self.assertEqual(fmt.format('test'), '"test"')

    def test_namespace(self):

        ns_dict = dict()

        fmt = CommandFormatter()
        fmt_json = CommandJSONFormatter()

        self.assertFalse(fmt.supports(ns_dict))
        self.assertFalse(fmt_json.supports(ns_dict))

        ns_dict = dict(json=False)

        self.assertFalse(fmt.supports(ns_dict))
        self.assertFalse(fmt_json.supports(ns_dict))

        ns_dict = dict(json=True)

        self.assertFalse(fmt.supports(ns_dict))
        self.assertTrue(fmt_json.supports(ns_dict))

        fmt_json.clear_argument(ns_dict)

        self.assertNotIn('json', ns_dict)
