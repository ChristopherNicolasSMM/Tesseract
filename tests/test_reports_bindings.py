"""Contratos de binding que protegem a futura composição de relatórios."""
import unittest
from addons.addon_reports.root.services.report_binding_service import ReportBindingService, BindingError


class ReportBindingTests(unittest.TestCase):
    def resolve(self, path, data, **kwargs):
        return ReportBindingService.resolve({'source': 'data', 'path': path, **kwargs}, data=data, parameters={})

    def test_preserves_null_false_zero(self):
        for value in (None, False, 0, '', []):
            with self.subTest(value=value):
                self.assertEqual(self.resolve(['value'], {'value': value}, fallback='other'), value)

    def test_missing_and_fallback(self):
        with self.assertRaises(BindingError) as result:
            self.resolve(['company', 'name'], {'company': {}})
        self.assertEqual(result.exception.path, ('company', 'name'))
        self.assertEqual(self.resolve(['value'], {}, fallback=None), None)

    def test_never_reads_attributes(self):
        with self.assertRaises(BindingError):
            self.resolve(['value', '__class__'], {'value': object()})

    def test_item_scope_is_explicit(self):
        binding = {'source': 'item', 'path': ['description']}
        with self.assertRaises(BindingError):
            ReportBindingService.resolve(binding, data={}, parameters={}, item={'description': 'Test'})
        self.assertEqual(ReportBindingService.resolve(binding, data={}, parameters={}, item={'description': 'Test'}, in_item_scope=True), 'Test')

    def test_invalid_paths_sources_and_extra_properties(self):
        for binding in ({'source': [], 'path': []}, {'source': 'data', 'path': '__class__'}, {'source': 'data', 'path': ['']}, {'source': 'data', 'path': ['x'] * 33}, {'source': 'data', 'path': [], 'expression': 'eval'}):
            with self.subTest(binding=binding), self.assertRaises(BindingError):
                ReportBindingService.resolve(binding, data={}, parameters={})

    def test_literal_dot_in_key(self):
        self.assertEqual(self.resolve(['a.b'], {'a.b': 10}), 10)

    def test_invalid_intermediate_is_not_hidden_by_fallback(self):
        with self.assertRaises(BindingError):
            self.resolve(['company', 'name'], {'company': None}, fallback='other')
