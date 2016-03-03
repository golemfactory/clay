from mock import patch

from golem.client import create_client, Client
from golem.clientconfigdescriptor import ClientConfigDescriptor
from golem.tools.testwithappconfig import TestWithAppConfig
from golem.tools.testwithdatabase import TestWithDatabase
from golem.environments.environment import Environment

class TestCreateClient(TestWithAppConfig):

    @patch('golem.client.Client')
    def test_config_default(self, mock_client):
        create_client()
        for name, args, kwargs in mock_client.mock_calls:
            if name == "":  # __init__ call
                config_desc = args[0]
                self.assertIs(type(config_desc), ClientConfigDescriptor)
                return
        self.fail("__init__ call not found")

    @patch('golem.client.Client')
    def test_config_override_valid(self, mock_client):
        self.assertTrue(hasattr(ClientConfigDescriptor(), "node_address"))
        create_client(node_address='1.0.0.0')
        for name, args, kwargs in mock_client.mock_calls:
            if name == "":  # __init__ call
                config_desc = args[0]
                self.assertEqual(config_desc.node_address, '1.0.0.0')
                return
        self.fail("__init__ call not found")

    @patch('golem.client.Client')
    def test_config_override_invalid(self, mock_client):
        """Test that create_client() does not allow to override properties
        that are not in ClientConfigDescriptor.
        """
        self.assertFalse(hasattr(ClientConfigDescriptor(), "node_colour"))
        with self.assertRaises(AttributeError):
            create_client(node_colour='magenta')


class TestClient(TestWithDatabase):

    def test_supported_task(self):
        c = Client(ClientConfigDescriptor())
        self.assertFalse(c.supported_task({}))
        task = {"environment": Environment.get_id(), 'max_price': 0}
        self.assertFalse(c.supported_task(task))
        e = Environment()
        e.accept_tasks = True
        c.config_desc.min_price = 10.0
        c.environments_manager.add_environment(e)
        self.assertFalse(c.supported_task(task))
        task["max_price"] = 10.0
        self.assertTrue(c.supported_task(task))
        task["max_price"] = 10.5
        self.assertTrue(c.supported_task(task))
        c.config_desc.min_price = 13.0
        self.assertFalse(c.supported_task(task))

    @patch("golem.client.Client.get_database_name")
    def test_add_to_waiting_payments(self, mock_database_name):
        mock_database_name.return_value = self.database.name
        c = Client(ClientConfigDescriptor())
        c.add_to_waiting_payments("xyz", "ABC", 10)
        incomes = c.transaction_system.get_incomes_list()
        self.assertEqual(len(incomes), 1)
        self.assertEqual(incomes[0]["node"], "ABC")
        self.assertEqual(incomes[0]["expected_value"], 10.0)
        self.assertEqual(incomes[0]["task"], "xyz")
        self.assertEqual(incomes[0]["value"], 0.0)

