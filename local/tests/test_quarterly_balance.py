"""Balance-sheet cells through normalization, the private ledger and bundle audit."""
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from local.bundle_audit import audit_bundle
from local.quarterly_import import main
from local.research import run


GENERAL_HEADER = (
    '出表日期,年度,季別,公司代號,公司名稱,流動資產,非流動資產,資產總計,流動負債,非流動負債,負債總計,'
    '股本,權益─具證券性質之虛擬通貨,資本公積,保留盈餘,其他權益,庫藏股票,歸屬於母公司業主之權益合計,'
    '共同控制下前手權益,合併前非屬共同控制股權,非控制權益,權益總計,待註銷股本股數（單位：股）,'
    '預收股款（權益項下）之約當發行股數（單位：股）,母公司暨子公司所持有之母公司庫藏股股數（單位：股）,每股參考淨值'
).split(',')


class BalanceImportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.manifest = self.root / 'manifest.json'
        self.output = self.root / 'normalized.json'
        self.dataset = 94831
        self.resource = 't187ap07_L_ci.csv'
        self.row = {'出表日期': '1091110', '年度': '109', '季別': '3', '公司代號': '1234',
                    '公司名稱': '合成企業', '流動資產': '--', '資產總計': '40', '負債總計': '0',
                    '權益總計': '40', '歸屬於母公司業主之權益合計': '-6', '每股參考淨值': '-0.35'}

    def save(self, columns=GENERAL_HEADER, observed='2020-11-10T06:00:00Z'):
        raw = self.root / f'{self.dataset}.response'
        with raw.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=columns, extrasaction='ignore')
            writer.writeheader()
            writer.writerow(self.row)
        body = raw.read_bytes()
        self.entry = dict(id=self.dataset, catalog=f'https://data.gov.tw/dataset/{self.dataset}',
                          url='https://mopsfin.twse.com.tw/opendata/' + self.resource,
                          received_at=observed, sha256=hashlib.sha256(body).hexdigest(),
                          bytes=len(body), exit=0, status='200')
        self.manifest.write_text(json.dumps([self.entry]))

    def normalize(self, *args):
        main(['--dataset', str(self.dataset), '--manifest', str(self.manifest),
              '--symbols', '1234', '--output', str(self.output), *args])
        return json.loads(self.output.read_bytes())

    def research(self):
        runs = self.root / 'runs'
        report = run(self.output, ['1234'], history_db=self.root / 'ledger.db',
                     output_root=runs, max_information_nodes=0)
        return audit_bundle(runs, report['run'])

    def test_equity_parent_equity_and_book_value_are_separate_period_end_observations(self):
        self.save()
        payload = self.normalize()
        bundle = self.research()
        facts = {f['metric']: f for f in bundle.facts['facts']}
        self.assertEqual({k: f['value'] for k, f in facts.items()},
                         {'total_assets': 40, 'total_liabilities': 0, 'total_equity': 40,
                          'equity_attributable_to_owners_of_parent': -6, 'book_value_per_share': -0.35})
        self.assertEqual(facts['book_value_per_share']['measure'], 'per_share')
        for fact in facts.values():
            self.assertEqual(fact['period_end'], '2020-09-30')
            self.assertEqual(fact['report_basis'], 'point_in_time')
            self.assertEqual(fact['unit'], 'source_reported')
            self.assertIsNone(fact['statement_scope'])
        self.assertEqual(payload['documents'][0]['stock_ids'], ['TW:1234'])
        self.assertEqual(payload['metadata']['missing_values'][0]['source_field'], '流動資產')

    def test_other_reviewed_resources_use_their_own_market_and_sector_headers(self):
        from local.quarterly_balance import ADDITIONAL_FIELDS
        identities = GENERAL_HEADER[:5]
        totals = ['資產總計', '負債總計', '權益總計', '歸屬於母公司業主之權益合計', '每股參考淨值']
        for dataset, filename, market, sector, column, metric in (
            (91967, 't187ap07_O_ci.csv', 'TPEx', 'general', '流動資產', 'current_assets'),
            (94829, 't187ap07_L_basi.csv', 'TWSE', 'financial', '貼現及放款－淨額', 'net_loans_and_discounts'),
            (94833, 't187ap07_L_ins.csv', 'TWSE', 'insurance', '保險合約資產', 'insurance_contract_assets'),
        ):
            with self.subTest(dataset=dataset):
                self.dataset, self.resource = dataset, filename
                self.output = self.root / f'normalized-{dataset}.json'
                self.row[column] = '1.5'
                self.save([*identities, *totals, column, *ADDITIONAL_FIELDS.get(sector, ())])
                payload = self.normalize()
                source, = payload['sources']
                self.assertEqual((source['market'], source['sector'], source['statement']),
                                 (market, sector, 'balance'))
                cell, = [r for r in payload['financial_metrics'] if r['source_field'] == column]
                self.assertEqual((cell['metric'], cell['value']), (metric, 1.5))

    def test_partial_sector_schema_or_flow_review_preserves_successful_output(self):
        self.save()
        self.normalize()
        before = self.output.read_bytes()
        review = self.root / 'review.json'
        review.write_text(json.dumps(dict(
            schema_version='quarterly-review-v1', dataset=self.dataset, raw_sha256=self.entry['sha256'],
            reviewed_at='2020-11-11T12:00:00Z', rows=[
                dict(stock_id='TW:1234', period_end='2020-09-30', source_field='資產總計',
                     raw_unit='TWD_thousands', reference_unit='TWD_thousands', reference_value='40',
                     statement_scope='consolidated', report_basis='cumulative',
                     reference_url='https://issuer.example/report.pdf', locator='p4')
            ])))
        with self.assertRaisesRegex(ValueError, 'basis'):
            self.normalize('--review', str(review))
        for label, columns, error in (
            ('new insurance field', [*GENERAL_HEADER, '保險合約資產'], 'unknown quarterly fields'),
            ('missing unselected column', [c for c in GENERAL_HEADER if c != '股本'], 'missing published fields'),
            ('changed selected column', ['權益總額' if c == '權益總計' else c for c in GENERAL_HEADER],
             'missing quarterly fields'),
        ):
            with self.subTest(label=label):
                self.save(columns)
                with self.assertRaisesRegex(ValueError, error):
                    self.normalize()
        self.assertEqual(self.output.read_bytes(), before)

    def test_conflicting_filings_preserve_prior_pointer_and_audited_facts(self):
        self.save()
        self.normalize()
        initial = self.research()
        pointer = self.root / 'runs/latest.json'
        original = pointer.read_bytes()
        self.row['權益總計'] = '42'
        self.save()
        self.output = self.root / 'conflicting.json'
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time revision'):
            self.research()
        self.assertEqual(pointer.read_bytes(), original)
        self.assertEqual(audit_bundle(self.root / 'runs', initial.report['run']).facts, initial.facts)

    def test_late_filings_do_not_replace_current_equity(self):
        self.save()
        self.normalize()
        self.research()
        for label, observed, equity in (
            ('corrected', '2020-11-12T06:00:00Z', '42'),
            ('late', '2020-11-11T06:00:00Z', '41'),
        ):
            self.row['權益總計'] = equity
            self.save(observed=observed)
            self.output = self.root / f'{label}.json'
            self.normalize()
            corrected, = [f for f in self.research().facts['facts'] if f['metric'] == 'total_equity']
            self.assertEqual(corrected['value'], 42)
