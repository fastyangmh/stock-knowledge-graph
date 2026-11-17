import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local.financial_review import review, main, tolerance
from local.research_history import canonical
from test_research_history import payload


def fixture(unit='TWD',period_type='month'):
    data=payload();m=data['financial_metrics'][0];m['unit']=unit;m['period_type']=period_type;m['currency']='TWD'
    if period_type == 'month':m.update(statement_scope='consolidated',report_basis='single_period')
    return data


class FinancialReviewTests(unittest.TestCase):
    def compare(self,a=None,b=None,**kw):
        return review(a or fixture(),b or fixture(),['1000'],**kw)
    def status(self,**kw):return self.compare(**kw)['rows'][0]['status']
    def test_exact_match_and_deterministic_report(self):
        a=self.compare();self.assertFalse(a['needs_review']);self.assertEqual(a['rows'][0]['difference'],'0');self.assertEqual(a,self.compare())
    def test_input_not_mutated(self):
        a=fixture();before=copy.deepcopy(a);self.compare(a,a);self.assertEqual(a,before)
    def test_decimal_precision_not_binary_float_subtraction(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['value']=0.3;b['financial_metrics'][0]['value']=0.1
        result=self.compare(a,b);self.assertEqual(result['rows'][0]['difference'],'0.2')
    def test_unknown_scale_even_equal_not_pass(self):
        for value in ('source_reported','',None,'unknown'):
            with self.subTest(value=value):self.assertEqual(self.status(a=fixture(value),b=fixture(value)),'unit_unverified')
    def test_different_units_not_converted(self):
        self.assertEqual(self.status(a=fixture('TWD'),b=fixture('TWD_thousands')),'unit_or_currency_mismatch')
    def test_different_currency_not_converted(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['currency']='TWD';b['financial_metrics'][0]['currency']='USD'
        self.assertEqual(self.status(a=a,b=b),'unit_or_currency_mismatch')
    def test_amount_difference_and_direction(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['value']=900
        row=self.compare(a,b)['rows'][0];self.assertEqual(row['status'],'value_mismatch');self.assertEqual(row['difference'],'-100')
    def test_tolerance_inclusive(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['value']=1001
        self.assertEqual(self.status(a=a,b=b,absolute_tolerance='1'),'within_tolerance')
        self.assertEqual(self.status(a=a,b=b,absolute_tolerance='.99'),'value_mismatch')
    def test_relative_fraction_explicit(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['value']=1010
        result=self.compare(a,b,relative_tolerance='.01');self.assertEqual(result['rows'][0]['status'],'within_tolerance')
        self.assertEqual(result['rows'][0]['allowed_difference'],'10.10')
    def test_zero_denominator_uses_difference_not_division(self):
        a,b=fixture(),fixture();a['financial_metrics'][0]['value']=0;b['financial_metrics'][0]['value']=0
        self.assertEqual(self.status(a=a,b=b),'equal')
    def test_missing_reference_not_zero(self):
        b=fixture();b['financial_metrics']=[];self.assertEqual(self.status(b=b),'missing_reference')
    def test_missing_input_not_zero(self):
        a=fixture();a['financial_metrics']=[];self.assertEqual(self.status(a=a),'missing_input')
    def test_no_records_is_not_success(self):
        a=fixture();a['financial_metrics']=[];result=self.compare(a,a)
        self.assertTrue(result['needs_review']);self.assertEqual(result['stocks_without_financial_records'],['TW:1000'])
    def test_duplicate_source_requires_selection(self):
        a=fixture();a['sources'].append({'source_id':'other','provider':'Other'})
        m=copy.deepcopy(a['financial_metrics'][0]);m['source_id']='other';a['financial_metrics'].append(m)
        self.assertEqual(self.status(a=a),'ambiguous_sources')
    def test_different_source_values_can_be_reviewed_not_auto_truth(self):
        b=fixture();b['sources'][0]['source_id']='other';b['financial_metrics'][0]['source_id']='other';b['documents'][0]['source_id']='other'
        result=self.compare(b=b);self.assertFalse(result['needs_review']);self.assertIn('no_automatic_truth_source_or_overwrite',result['notes'])
    def test_quarterly_scope_and_basis_required(self):
        self.assertEqual(self.status(a=fixture(period_type='quarter'),b=fixture(period_type='quarter')),'statement_definition_unverified')
    def test_cumulative_not_same_as_single_quarter(self):
        a,b=fixture(period_type='quarter'),fixture(period_type='quarter')
        for data in (a,b):data['financial_metrics'][0].update(statement_scope='consolidated',report_basis='cumulative')
        b['financial_metrics'][0]['report_basis']='single_period'
        self.assertEqual(self.status(a=a,b=b),'statement_definition_mismatch')
    def test_consolidated_not_same_as_separate(self):
        a,b=fixture(period_type='quarter'),fixture(period_type='quarter')
        for data in (a,b):data['financial_metrics'][0].update(statement_scope='consolidated',report_basis='point_in_time')
        b['financial_metrics'][0]['statement_scope']='separate'
        self.assertEqual(self.status(a=a,b=b),'statement_definition_mismatch')
    def test_full_definition_matches(self):
        a=fixture(period_type='quarter');a['financial_metrics'][0].update(statement_scope='consolidated',report_basis='cumulative')
        self.assertEqual(self.status(a=a,b=a),'equal')
    def test_invalid_tolerance_rejected(self):
        for value in (True,'nan','inf','-1','x','1e100'):
            with self.subTest(value=value),self.assertRaises(ValueError):tolerance(value)
    def test_row_budget(self):
        a=fixture();m=copy.deepcopy(a['financial_metrics'][0]);m['metric']='extra';a['financial_metrics'].append(m)
        with self.assertRaisesRegex(ValueError,'budget'):self.compare(a,a,max_rows=1)
    def test_no_network_and_no_source_modification(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a.json';b=root/'b.json';out=root/'review.json';a.write_bytes(canonical(fixture()));b.write_bytes(a.read_bytes());old=a.read_bytes()
            with patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('no network')),redirect_stdout(io.StringIO()):
                self.assertEqual(main(['--input',str(a),'--reference',str(b),'--symbols','1000','--output',str(out)]),0)
            self.assertEqual(a.read_bytes(),old);self.assertEqual(b.read_bytes(),old);self.assertFalse(json.loads(out.read_text())['needs_review'])
    def test_cli_needs_review_exit_two_and_report_written(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);a=root/'a.json';b=root/'b.json';out=root/'review.json';a.write_bytes(canonical(fixture('source_reported')));b.write_bytes(a.read_bytes())
            with redirect_stdout(io.StringIO()):self.assertEqual(main(['--input',str(a),'--reference',str(b),'--symbols','1000','--output',str(out)]),2)
            self.assertTrue(json.loads(out.read_text())['needs_review'])
    def test_cli_rejects_source_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            a=Path(d)/'a.json';a.write_bytes(canonical(fixture()))
            with patch('sys.stderr',io.StringIO()),self.assertRaises(SystemExit):main(['--input',str(a),'--reference',str(a),'--symbols','1000','--output',str(a)])

class CurrencySafetyTests(unittest.TestCase):
    def test_unknown_currency_never_passes_equal_amounts(self):
        for currency in (None, '', 'unknown', 'source_reported', 'UNKNOWN', ' unknown ', ' ', 'N/A'):
            with self.subTest(currency=currency):
                a = fixture()
                a['financial_metrics'][0]['currency'] = currency
                result = review(a, a, ['1000'])
                self.assertTrue(result['needs_review'])
                self.assertEqual(result['rows'][0]['status'], 'currency_unverified')

    def test_conflicting_scope_alias_cannot_pass(self):
        a = fixture()
        a['financial_metrics'][0].update(statement_scope='consolidated', consolidation='separate',
                                         report_basis='single_period', value_basis='single_period')
        with self.assertRaisesRegex(ValueError, 'conflicting.*definition'):
            review(a, a, ['1000'])

    def test_aliases_resolve_to_the_same_review_definition(self):
        a, b = fixture(), fixture()
        a['financial_metrics'][0].update(statement_scope='consolidated', report_basis='single_period')
        b['financial_metrics'][0].pop('statement_scope');b['financial_metrics'][0].pop('report_basis')
        b['financial_metrics'][0].update(consolidation='consolidated', value_basis='single_period')
        self.assertFalse(review(a, b, ['1000'])['needs_review'])

    def test_monthly_scope_and_basis_must_be_verified(self):
        a = fixture()
        a['financial_metrics'][0].pop('statement_scope')
        result = review(a, a, ['1000'])
        self.assertEqual(result['rows'][0]['status'], 'statement_definition_unverified')

    def test_changed_normalization_version_requires_review(self):
        a, b = fixture(), fixture()
        a['financial_metrics'][0]['normalization_version'] = 'units-v2'
        b['financial_metrics'][0]['normalization_version'] = 'units-v1'
        self.assertEqual(review(a,b,['1000'])['rows'][0]['status'],'normalization_version_mismatch')
