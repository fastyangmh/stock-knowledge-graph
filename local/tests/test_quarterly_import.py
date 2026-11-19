"""Private quarterly CSV -> normalized input -> SQLite research and audited facts."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from local.bundle_audit import audit_bundle
from local.research import run


class QuarterlyImportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.manifest = self.root / 'manifest.json'
        self.output = self.root / 'input.json'
        self.columns = '出表日期,年度,季別,公司代號,公司名稱,營業收入,營業利益（損失）,本期淨利（淨損）,基本每股盈餘（元）'
        self.row = '1091110,109,3,1234,測試企業,0,-123,--,-0.1'
        self.raw = self.root / '91998.response'
        self.save(self.columns, self.row)

    def save(self, columns, row):
        from local.quarterly_income import ADDITIONAL_FIELDS
        sector = {'91995': 'financial', '92000': 'insurance'}.get(self.raw.stem, 'general')
        unused = ADDITIONAL_FIELDS[sector]
        columns = columns + ',' + ','.join(unused)
        row = '\n'.join(line + ',' * len(unused) for line in row.splitlines())
        raw = (columns + '\n' + row + '\n').encode('utf-8-sig')
        self.raw.write_bytes(raw)
        self.entry = dict(id=91998, url='https://mopsfin.twse.com.tw/opendata/t187ap06_L_ci.csv',
                          catalog='https://data.gov.tw/dataset/91998', status='200', exit=0,
                          received_at='2020-11-10T02:00:00+00:00', bytes=len(raw),
                          sha256=hashlib.sha256(raw).hexdigest())
        self.manifest.write_text(json.dumps([self.entry]))

    def normalize(self, *options):
        from local.quarterly_import import main
        main(['--manifest', str(self.manifest), '--dataset', '91998', '--symbols', '1234',
              '--output', str(self.output), *options])

    def research(self):
        runs = self.root / 'runs'
        report = run(self.output, ['1234'], history_db=self.root/'ledger.db',
                     output_root=runs, max_information_nodes=0)
        return audit_bundle(runs, report['run'])

    def test_raw_amounts_per_share_and_missing_survive_display_clipping(self):
        self.normalize()
        bundle = self.research()
        facts = {f['source_field']: f for f in bundle.facts['facts']}
        self.assertEqual({k:f['value'] for k,f in facts.items()},
                         {'營業收入':0, '營業利益（損失）':-123, '基本每股盈餘（元）':-0.1})
        self.assertEqual(facts['營業收入']['period_end'], '2020-09-30')
        self.assertEqual(facts['營業收入']['unit'], 'source_reported')
        self.assertEqual(facts['基本每股盈餘（元）']['measure'], 'per_share')
        self.assertIsNone(facts['營業收入']['report_basis'])
        self.assertEqual(facts['營業收入']['raw_sha256'], self.entry['sha256'])
        self.assertEqual(facts['營業收入']['source_available_at'], self.entry['received_at'])
        normalized = json.loads(self.output.read_text())
        self.assertEqual(normalized['documents'][0]['stock_ids'], ['TW:1234'])
        self.assertEqual(normalized['metadata']['missing_values'][0]['source_field'], '本期淨利（淨損）')

    def test_only_exact_issuer_cells_acquire_reviewed_units_and_basis(self):
        common = dict(stock_id='TW:1234', period_end='2020-09-30', statement_scope='consolidated',
                      reference_url='https://issuer.example/2020q3.pdf')
        review = dict(schema_version='quarterly-review-v1', dataset=91998, raw_sha256=self.entry['sha256'],
                      reviewed_at='2020-11-11T08:00:00Z', rows=[
                          dict(common, source_field='營業利益（損失）', raw_unit='TWD_thousands',
                               reference_unit='TWD_millions', reference_value='-0.123',
                               report_basis='cumulative', locator='p.3 January through September operating loss'),
                          dict(common, source_field='基本每股盈餘（元）', raw_unit='TWD_per_share',
                               reference_unit='TWD_per_share', reference_value='-0.09',
                               report_basis='single_period', locator='p.4 Q3 EPS')])
        path = self.root / 'review.json'
        path.write_text(json.dumps(review))
        self.normalize('--review', str(path))
        bundle = self.research()
        facts = {f['source_field']: f for f in bundle.facts['facts']}
        income = facts['營業利益（損失）']
        self.assertEqual((income['value'], income['unit'], income['report_basis']),
                         (-123, 'TWD_thousands', 'cumulative'))
        self.assertEqual(income['observed_at'], '2020-11-10T02:00:00.000000+00:00')
        self.assertEqual(income['source_available_at'], '2020-11-11T08:00:00+00:00')
        self.assertEqual(income['issuer_review']['locator'], 'p.3 January through September operating loss')
        eps = facts['基本每股盈餘（元）']
        self.assertEqual(eps['issuer_review']['status'], 'value_mismatch')
        self.assertIsNone(eps['report_basis'])
        self.assertIsNone(facts['營業收入']['currency'])
        review['rows'][1]['reference_value'] = '-0.10'
        path.write_text(json.dumps(review))
        self.output = self.root/'rechecked.json'
        self.normalize('--review', str(path))
        eps = json.loads(self.output.read_text())['financial_metrics'][-1]
        self.assertEqual((eps['unit'], eps['report_basis']), ('TWD_per_share', 'single_period'))

    def test_later_review_of_older_source_does_not_replace_a_newer_filing(self):
        path = self.root/'review.json'
        path.write_text(json.dumps(dict(schema_version='quarterly-review-v1', dataset=91998,
            raw_sha256=self.entry['sha256'], reviewed_at='2020-11-15T08:00:00Z', rows=[
            dict(stock_id='TW:1234', period_end='2020-09-30', statement_scope='consolidated',
                 reference_url='https://issuer.example/q3.pdf', source_field='營業利益（損失）',
                 raw_unit='TWD_thousands', reference_unit='TWD_thousands', reference_value='-123',
                 report_basis='cumulative', locator='p.3 operating income')])))
        self.normalize('--review', str(path))
        self.research()
        self.output = self.root/'new.json'
        self.save(self.columns, self.row.replace('-123', '-124'))
        self.entry['received_at'] = '2020-11-12T02:00:00+00:00'
        self.manifest.write_text(json.dumps([self.entry]))
        self.normalize()
        facts = self.research().facts['facts']
        income = next(f for f in facts if f['source_field'] == '營業利益（損失）')
        self.assertEqual(income['value'], -124)

    def test_market_and_sector_resource_selects_its_own_fields(self):
        from local.quarterly_import import main
        for dataset, filename, fields, expected in (
            (94853, 't187ap06_O_ci.csv', self.columns.split(',')[5:], 'revenue'),
            (91995, 't187ap06_L_basi.csv', ['利息淨收益','本期稅後淨利（淨損）','基本每股盈餘（元）'], 'net_interest_income'),
            (92000, 't187ap06_L_ins.csv', ['保險服務結果','本期淨利（淨損）','基本每股盈餘'], 'insurance_service_result'),
        ):
            with self.subTest(dataset=dataset):
                columns = self.columns.split(',')[:5] + fields
                self.raw = self.root/f'{dataset}.response'
                self.save(','.join(columns), ','.join(self.row.split(',')[:5] + ['3'] * len(fields)))
                self.entry.update(id=dataset, url='https://mopsfin.twse.com.tw/opendata/' + filename,
                                  catalog=f'https://data.gov.tw/dataset/{dataset}')
                self.manifest.write_text(json.dumps([self.entry]))
                output = self.root/f'{dataset}.json'
                main(['--manifest',str(self.manifest),'--dataset',str(dataset),'--symbols','1234','--output',str(output)])
                fact = json.loads(output.read_text())['financial_metrics'][0]
                self.assertEqual(fact['metric'], expected)
                self.assertEqual(fact['unit'], 'source_reported')

    def test_rejected_input_preserves_prior_normalization_and_bundle(self):
        self.normalize()
        self.research()
        before = self.output.read_bytes()
        pointer = self.root / 'runs/latest.json'
        prior = pointer.read_bytes()
        cases = (
            ('raw', 'checksum'), ('resource', 'resource'), ('duplicate', 'duplicate'),
            ('missing', 'missing quarterly fields'), ('extra', 'unknown quarterly fields'),
            ('malformed', 'CSV'), ('absent issuer', 'no observation'), ('mixed', 'mixed quarterly'),
        )
        for case, error in cases:
            with self.subTest(case=case):
                self.save(self.columns, self.row)
                if case == 'raw':
                    self.raw.write_bytes(self.raw.read_bytes() + b' ')
                elif case == 'resource':
                    self.entry['url'] += '?unreviewed=1'
                    self.manifest.write_text(json.dumps([self.entry]))
                elif case == 'duplicate':
                    self.save(self.columns, self.row + '\n' + self.row)
                elif case == 'missing':
                    self.save(self.columns.replace('營業收入', 'x'), self.row)
                elif case == 'extra':
                    self.save(self.columns + ',本季營業收入', self.row + ',10')
                elif case == 'malformed':
                    self.save(self.columns, self.row[:-4] + '"-0.1')
                elif case == 'absent issuer':
                    self.save(self.columns, self.row.replace('1234', '4321'))
                elif case == 'mixed':
                    earlier = self.row.replace('109,3,1234', '109,2,4321')
                    self.save(self.columns, self.row + '\n' + earlier)
                with self.assertRaisesRegex(ValueError, error):
                    self.normalize()
                self.assertEqual(self.output.read_bytes(), before)
                self.assertEqual(pointer.read_bytes(), prior)

    def test_conflicting_simultaneous_filing_retains_latest_audited_bundle(self):
        self.normalize()
        bundle = self.research()
        pointer = self.root/'runs/latest.json'
        original = pointer.read_bytes()
        self.output = self.root/'conflicting.json'
        self.save(self.columns, self.row.replace('-123', '-124'))
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time revision'):
            self.research()
        self.assertEqual(pointer.read_bytes(), original)
        self.assertEqual(audit_bundle(self.root/'runs', bundle.report['run']).facts, bundle.facts)

    def test_changed_review_cannot_attach_to_new_raw_bytes_or_unknown_stock(self):
        review = dict(schema_version='quarterly-review-v1', dataset=91998, raw_sha256=self.entry['sha256'],
                      reviewed_at='2020-11-11T02:00:00Z', rows=[
                          dict(stock_id='TW:9999', period_end='2020-09-30', source_field='營業收入')])
        path = self.root/'review.json'
        path.write_text(json.dumps(review))
        with self.assertRaisesRegex(ValueError, 'unresolved'):
            self.normalize('--review', str(path))
        self.save(self.columns, self.row.replace('-123', '-124'))
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.normalize('--review', str(path))
        self.assertFalse(self.output.exists())

    def test_ambiguous_acquisition_metadata_does_not_enter_research(self):
        body = json.dumps(self.entry)
        self.manifest.write_text('[{"url":"https://unreviewed.example/a.csv",' + body[1:] + ']')
        with self.assertRaisesRegex(ValueError, 'duplicate JSON key'):
            self.normalize()
        self.assertFalse(self.output.exists())

    def test_company_with_only_missing_values_cannot_count_as_a_financial_sample(self):
        self.save(self.columns, '1091110,109,3,1234,測試企業,--,,N/A,-')
        with self.assertRaisesRegex(ValueError, 'no numeric observation.*1234'):
            self.normalize()
        self.assertFalse(self.output.exists())
