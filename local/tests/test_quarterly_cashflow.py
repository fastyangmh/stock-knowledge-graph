"""Synthetic, offline notes exercise the reviewed issuer layout through CLI and audit."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.bundle_audit import audit_bundle
from local.research import run


class CashflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.notes = self.root / 'notes.json'
        self.output = self.root / 'normalized.json'
        prefix = ('https://www.sas-globalwafers.com/wp-content/uploads/2025/11/'
                  'GlobalWafers_2025Q3-consolidated-financial-statement_')
        self.data = dict(schema_version='issuer-cashflow-notes-v1', symbol='6488',
                         period_end='2025-09-30', observed_at='2025-11-20T08:00:00Z', editions=[])
        for language, values in [('CN', ['(1,234)', '0', '--', '35', '19', '(16)']),
                                 ('EN', ['-1234', '0', '-', '35', '19', '-16'])]:
            metrics = ['operating_cash_flow', 'investing_cash_flow', 'financing_cash_flow',
                       'opening_cash_equivalents', 'closing_cash_equivalents', 'net_change_cash_equivalents']
            cells = {metric: dict(locator=f'page 7, test column, {metric}', raw_value=value)
                     for metric, value in zip(metrics, values, strict=True)}
            self.data['editions'].append(dict(
                url=prefix+language+'.pdf', cells=cells,
                context=dict(period_start='2025-01-01', period_end='2025-09-30', unit='TWD_thousands',
                             statement_scope='consolidated', report_basis='cumulative')))

    def normalize(self):
        from local.quarterly_cashflow import main
        body = json.dumps(self.data).encode()
        self.notes.write_bytes(body)
        main(['--notes', str(self.notes), '--sha256', hashlib.sha256(body).hexdigest(),
              '--output', str(self.output)])

    def research(self):
        runs = self.root / 'runs'
        report = run(self.output, ['6488'], history_db=self.root/'ledger.db', output_root=runs,
                     max_information_nodes=0)
        return audit_bundle(runs, report['run'])

    def test_signed_flows_and_balance_boundaries_survive_research_and_audit(self):
        self.normalize()
        bundle = self.research()
        facts = {f['metric']: f for f in bundle.facts['facts']}
        self.assertEqual(len(facts), 5)
        self.assertEqual(facts['investing_cash_flow']['value'], 0)
        flow = facts['operating_cash_flow']
        self.assertEqual((flow['value'], flow['report_basis'], flow['period_start'], flow['unit']),
                         (-1234, 'cumulative', '2025-01-01', 'TWD_thousands'))
        self.assertEqual((flow['source']['market'], flow['currency'], flow['statement_scope']),
                         ('TPEx', 'TWD', 'consolidated'))
        self.assertEqual(flow['note_sha256'], hashlib.sha256(self.notes.read_bytes()).hexdigest())
        self.assertEqual(facts['opening_cash_equivalents']['instant_date'], '2025-01-01')
        self.assertEqual(facts['closing_cash_equivalents']['instant_date'], '2025-09-30')
        self.assertEqual(facts['closing_cash_equivalents']['report_basis'], 'point_in_time')
        payload = json.loads(self.output.read_bytes())
        self.assertEqual(payload['metadata']['missing_values'][0]['metric'], 'financing_cash_flow')
        self.assertEqual(payload['documents'][0]['stock_ids'], ['TW:6488'])
        self.assertNotIn('raw_sha256', flow)

    def test_rejected_notes_preserve_previous_output_and_audit(self):
        import copy
        self.normalize()
        bundle = self.research()
        valid = copy.deepcopy(self.data)
        good_path = self.output
        before = good_path.read_bytes()
        self.output = self.root / 'rejected.json'
        latest = (self.root/'runs/latest.json').read_bytes()
        for problem in ('empty locator', 'changed field', 'unsupported issuer', 'unexpected unit',
                        'same document', 'different values', 'too early', 'no amounts', 'empty parentheses'):
            with self.subTest(problem=problem):
                self.data = copy.deepcopy(valid)
                primary, reference = self.data['editions']
                cell = primary['cells']['operating_cash_flow']
                if problem == 'empty locator':
                    cell['locator'] = '  '
                elif problem == 'changed field':
                    primary['cells']['profit'] = primary['cells'].pop('operating_cash_flow')
                elif problem == 'unsupported issuer':
                    self.data['symbol'] = '1234'
                elif problem == 'unexpected unit':
                    reference['context']['unit'] = 'USD'
                elif problem == 'same document':
                    reference['url'] = primary['url']
                elif problem == 'different values':
                    cell['raw_value'] = '999'
                elif problem == 'too early':
                    self.data['observed_at'] = '2025-10-01T00:00:00Z'
                elif problem == 'no amounts':
                    for edition in self.data['editions']:
                        for item in edition['cells'].values():
                            item['raw_value'] = '--'
                else:
                    for edition in self.data['editions']:
                        edition['cells']['operating_cash_flow']['raw_value'] = '()'
                with self.assertRaises(ValueError):
                    self.normalize()
                self.assertFalse(self.output.exists())
                self.assertEqual(before, good_path.read_bytes())
                self.assertEqual(latest, (self.root/'runs/latest.json').read_bytes())
        self.assertEqual(audit_bundle(self.root/'runs', bundle.report['run']).facts, bundle.facts)

    def test_changed_note_or_simultaneous_revision_preserves_prior_bundle(self):
        from local.quarterly_cashflow import main
        self.normalize()
        first = self.research()
        before = (self.root/'runs/latest.json').read_bytes()
        self.output = self.root/'second.json'
        with self.assertRaisesRegex(ValueError, 'checksum'):
            main(['--notes', str(self.notes), '--sha256', '0'*64, '--output', str(self.output)])
        self.assertFalse(self.output.exists())
        for edition in self.data['editions']:
            edition['cells']['investing_cash_flow']['raw_value'] = '2'
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time revision'):
            self.research()
        self.assertEqual(before, (self.root/'runs/latest.json').read_bytes())
        self.assertEqual(first.facts, audit_bundle(self.root/'runs', first.report['run']).facts)

    def test_later_recheck_supersedes_earlier_observation(self):
        self.normalize()
        old = self.research()
        for edition in self.data['editions']:
            edition['cells']['investing_cash_flow']['raw_value'] = '2'
        self.output = self.root/'later.json'
        self.data['observed_at'] = '2025-11-21T08:00:00Z'
        self.normalize()
        new = self.research()
        fact = next(f for f in new.facts['facts'] if f['metric'] == 'investing_cash_flow')
        self.assertEqual(fact['value'], 2)
        first = next(f for f in old.facts['facts'] if f['metric'] == 'investing_cash_flow')
        self.assertEqual(first['value'], 0)
