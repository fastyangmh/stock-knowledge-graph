"""Synthetic source bytes through official import, research and bundle audit."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local.collect_official import download
from local.official_import import main as import_main
from local.research import run
from local.bundle_audit import audit_bundle
from local.research_history import canonical
from test_official_adapter import COMPANY, REVENUE, REGISTRY, WHEN

VERSION = 'official-monthly-twd-v1'


class FinancialUnitsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with patch('local.collect_official.fetch_csv', side_effect=[COMPANY, REVENUE]), patch('local.collect_official.now',return_value=WHEN), patch('local.collect_official.time.sleep'):
            download(REGISTRY, self.root/'raw')
        proof = b'Synthetic independent statement: TWD thousands; consolidated monthly revenue.'
        (self.root/'statement.txt').write_bytes(proof)
        self.evidence = {'schema_version':'financial-unit-evidence-1.0', 'normalization_version':VERSION,
            'decisions':[{'source_id':'twse_monthly_revenue','stock_id':'TW:2330','period_end':'2026-10-31',
                'raw_snapshot_sha256':hashlib.sha256(REVENUE).hexdigest(), 'raw_unit':'TWD_thousands',
                'currency':'TWD','statement_scope':'consolidated','report_basis':'single_period',
                'references':[{'path':'statement.txt','sha256':hashlib.sha256(proof).hexdigest(),
                    'url':'https://example.org/independent-statement','locator':'monthly revenue table'}]}]}
        self.proof = self.root/'evidence.json';self.proof.write_bytes(canonical(self.evidence))

    def normalize(self, evidence=True):
        output = self.root/('v2.json' if evidence else 'v1.json')
        args = ['--snapshot-dir',str(self.root/'raw'),'--symbols','2330','--as-of','2026-11-15','--output',str(output)]
        if evidence:args += ['--unit-evidence',str(self.proof)]
        import_main(args)
        return output

    def test_verified_units_preserve_raw_and_availability_through_audited_research(self):
        old = json.loads(self.normalize(False).read_text())
        path = self.normalize();new = json.loads(path.read_text())
        amount = next(r for r in new['financial_metrics'] if r['metric']=='monthly_revenue')
        self.assertEqual((amount['value'],amount['unit'],amount['currency']), (1000000,'TWD','TWD'))
        self.assertEqual((amount['raw_value'],amount['raw_unit']), (1000,'TWD_thousands'))
        self.assertEqual(amount['available_at'],WHEN)
        self.assertEqual(amount['normalization_version'],VERSION)
        self.assertEqual(old['financial_metrics'][0]['unit'],'source_reported')
        report = run(path,['2330'],history_db=self.root/'v2.db',output_root=self.root/'runs')
        audited = audit_bundle(self.root/'runs',report['run'])
        fact = next(f for f in audited.facts['facts'] if f['metric']=='monthly_revenue')
        self.assertEqual((fact['consolidation'],fact['value_basis']),('consolidated','single_period'))
        self.assertEqual(fact['value'],1000000)
        self.assertEqual(fact['normalization']['raw_snapshot_sha256'],hashlib.sha256(REVENUE).hexdigest())

    def test_new_unit_version_refuses_old_ledger_and_preserves_old_bundle(self):
        old = self.normalize(False)
        first = run(old,['2330'],history_db=self.root/'old.db',output_root=self.root/'old-runs')
        before = (self.root/'old-runs'/first['run']/'research-facts.json').read_bytes()
        pointer = (self.root/'old-runs'/'latest.json').read_bytes()
        with self.assertRaisesRegex(ValueError,'normalization version.*separate ledger'):
            run(self.normalize(),['2330'],history_db=self.root/'old.db',output_root=self.root/'old-runs')
        self.assertEqual((self.root/'old-runs'/'latest.json').read_bytes(),pointer)
        self.assertEqual((self.root/'old-runs'/first['run']/'research-facts.json').read_bytes(),before)
        self.assertEqual(next(f for f in audit_bundle(self.root/'old-runs',first['run']).facts['facts'] if f['metric']=='monthly_revenue')['unit'],'source_reported')

    def test_reviewed_monthly_and_quarterly_share_ledger_without_rebasing_monthly(self):
        from local.tests.quarterly_fixtures import normalize_csv, research, save_csv
        monthly = self.normalize()
        first = research(self.root, monthly, '2330')
        row = {'出表日期': '1091110', '年度': '109', '季別': '3', '公司代號': '2330',
               '公司名稱': '測試公司', '資產總計': '80'}
        save_csv(self.root, 94831, 't187ap07_L_ci.csv', row)
        balance = self.root/'balance.json'
        normalize_csv(self.root/'manifest.json', 94831, '2330', balance)
        combined = research(self.root, balance, '2330')
        self.assertEqual({r['source_id'] for r in combined.facts['facts']},
                         {'twse_monthly_revenue', 'mops_94831'})
        self.assertEqual(research(self.root, monthly, '2330', known_at=first.facts['scope']['known_at']).facts,
                         first.facts)
        with self.assertRaisesRegex(ValueError, 'normalization version.*separate ledger'):
            research(self.root, self.normalize(False), '2330')

    def test_monthly_fact_cannot_redeclare_another_version_under_same_policy(self):
        path = self.normalize()
        data = json.loads(path.read_bytes())
        data['financial_metrics'][0]['normalization_version'] = 'unreviewed-replacement'
        path.write_bytes(canonical(data))
        with self.assertRaisesRegex(ValueError, 'normalization version'):
            run(path, ['2330'], history_db=self.root/'ledger.db', output_root=self.root/'runs')

    def test_empty_review_and_tampered_evidence_are_rejected(self):
        # Empty decisions are not a successful unit review.
        original = copy.deepcopy(self.evidence)
        self.evidence['decisions'] = []
        self.proof.write_bytes(canonical(self.evidence))
        with self.assertRaisesRegex(ValueError,'decisions'):
            self.normalize()
        self.proof.write_bytes(canonical(original))
        (self.root/'statement.txt').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'checksum'):
            self.normalize()

    def test_evidence_is_bound_to_exact_raw_source_snapshot(self):
        self.evidence['decisions'][0]['raw_snapshot_sha256'] = '0'*64
        self.proof.write_bytes(canonical(self.evidence))
        with self.assertRaisesRegex(ValueError,'raw snapshot mismatch'):
            self.normalize()

    def test_import_rejects_evidence_output_collision_before_any_bytes_change(self):
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'output.*input|output.*evidence'):
            import_main(['--snapshot-dir',str(self.root/'raw'),'--symbols','2330',
                         '--as-of','2026-11-15','--unit-evidence',str(self.proof),
                         '--output',str(self.proof)])
        self.assertEqual({p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)

    def test_import_preserves_references_snapshots_and_selection_inputs(self):
        registry = self.root/'registry.json'
        registry.write_bytes(Path(REGISTRY).read_bytes())
        universe, holdings = self.root/'universe.csv', self.root/'holdings.csv'
        universe.write_text('retained selection input')
        holdings.write_text('retained holdings input')
        snapshot_files = [p for p in (self.root/'raw').rglob('*') if p.is_file()]
        targets = [self.root/'statement.txt', registry, universe, holdings, *snapshot_files]
        before = {p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        for target in targets:
            for path, body in before.items():
                path.write_bytes(body)
            with self.subTest(target=target.name):
                selection = (['--universe',str(universe),'--etf-holdings',str(holdings),
                              '--universe-source','https://example.org/universe']
                             if target in (universe, holdings) else ['--symbols','2330'])
                with self.assertRaisesRegex(ValueError, 'output.*input|output.*evidence'):
                    import_main(['--snapshot-dir',str(self.root/'raw'),'--registry',str(registry),
                                 *selection,'--as-of','2026-11-15','--unit-evidence',str(self.proof),
                                 '--output',str(target)])
                self.assertEqual({p: p.read_bytes() for p in self.root.rglob('*') if p.is_file()}, before)
