import unittest
import mock

import kojihub


class TestListing(unittest.TestCase):
    def setUp(self):
        self.hub = kojihub.RootExports()
        self.standard_processor_kwargs = dict(
            tables=mock.ANY,
            columns=mock.ANY,
            values=mock.ANY,
            joins=mock.ANY,
            clauses=mock.ANY,
            opts=mock.ANY,
            aliases=mock.ANY,
        )

    @mock.patch('kojihub.QueryProcessor')
    def test_list_tasks_basic_invocation(self, processor):
        generator = self.hub.listTasks()
        results = list(generator)  # Exhaust the generator
        processor.assert_called_once_with(**self.standard_processor_kwargs)

    @mock.patch('kojihub.QueryProcessor')
    def test_list_tasks_by_owner(self, processor):
        generator = self.hub.listTasks(opts={'owner': 1})
        results = list(generator)  # Exhaust the generator
        arguments = self.standard_processor_kwargs.copy()
        arguments['clauses'] = ['owner = %(owner)i']
        processor.assert_called_once_with(**arguments)
        self.assertEqual(results, [])

    @mock.patch('kojihub.QueryProcessor')
    def test_list_tasks_by_not_owner(self, processor):
        generator = self.hub.listTasks(opts={'not_owner': 1})
        results = list(generator)  # Exhaust the generator
        arguments = self.standard_processor_kwargs.copy()
        arguments['clauses'] = ['owner != %(not_owner)i']
        processor.assert_called_once_with(**arguments)
        self.assertEqual(results, [])

    @mock.patch('kojihub.QueryProcessor')
    def test_list_tasks_by_arch(self, processor):
        generator = self.hub.listTasks(opts={'arch': ['x86_64']})
        results = list(generator)  # Exhaust the generator
        arguments = self.standard_processor_kwargs.copy()
        arguments['clauses'] = ['arch IN %(arch)s']
        processor.assert_called_once_with(**arguments)
        self.assertEqual(results, [])

    @mock.patch('kojihub.QueryProcessor')
    def test_list_tasks_by_not_arch(self, processor):
        generator = self.hub.listTasks(opts={'not_arch': ['x86_64']})
        results = list(generator)  # Exhaust the generator
        arguments = self.standard_processor_kwargs.copy()
        arguments['clauses'] = ['arch NOT IN %(not_arch)s']
        processor.assert_called_once_with(**arguments)
        self.assertEqual(results, [])

