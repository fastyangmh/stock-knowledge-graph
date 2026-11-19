"""Synthetic saved receipt through private import, SQLite research and bundle audit."""
import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from local.bundle_audit import audit_bundle
from local.research import run

DAY = '2020-01-02'
RECEIVED = '2020-01-03T08:10:00+00:00'
CATALOG = 'https://data.gov.tw/dataset/11856'
RESOURCE = 'https://www.tpex.org.tw/web/stock/3insti/DAILY_TradE/3itrade_hedge_result.php?l=zh-tw&o=data&se=EW&t=D'
GROUPS = ('外資及陸資不含外資自營商', '外資自營商', '外資及陸資', '投信', '自營商自行買賣', '自營商避險', '自營商')
FIELDS = ['資料日期', '代號', '名稱', *(g+s for g in GROUPS for s in ('買進股數', '賣出股數', '買賣超股數')), '三大法人買賣超股數合計']
# Source total is kept as reported. Foreign dealer activity is nonzero here.
ROW = ['1090102', '1000', '合成公司', '1,100', 1102, -2, 4, 5, -1, 1104, 1107, -3,
       0, 2, -2, 5, 3, 2, 0, 1, -1, 5, 4, 1, -3]


class InstitutionalImportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        self.manifest = self.raw/'manifest.json'
        self.output = self.root/'normalized.json'
        self.runs = self.root/'runs'

    def capture(self, rows=(ROW,), fields=FIELDS, received=RECEIVED):
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerows([fields, *rows])
        body = stream.getvalue().encode('utf-8-sig')
        (self.raw/'11856.response').write_bytes(body)
        entry = dict(id=11856, url=RESOURCE, catalog=CATALOG, started_at=received, received_at=received,
                     status='200', exit=0, error='', mime='application/csv;charset=utf-8',
                     bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        self.manifest.write_text(json.dumps([entry]))
        return entry['sha256']

    def normalize(self):
        from local.institutional_import import main
        main(['--manifest', str(self.manifest), '--trade-date', DAY, '--symbols', '1000',
              '--output', str(self.output)])

    def research(self, **kwargs):
        report = run(self.output, ['1000'], history_db=self.root/'ledger.db',
                     output_root=self.runs, **kwargs)
        return audit_bundle(self.runs, report['run'])

    def test_class_and_source_total_remain_separate_locatable_numeric_facts(self):
        checksum = self.capture()
        self.normalize()
        bundle = self.research()
        facts = {f['source_column']: f for f in bundle.facts['facts']}
        self.assertEqual(len(facts), 22)
        for column, value in [('外資及陸資不含外資自營商買進股數', 1100), ('外資自營商買賣超股數', -1),
                              ('投信買進股數', 0), ('三大法人買賣超股數合計', -3)]:
            fact = facts[column]
            self.assertEqual((fact['value'], fact['unit'], fact['kind']), (value, 'shares', 'chip_metric'))
            self.assertEqual((fact['trade_date'], fact['raw_sha256'], fact['row_number']), (DAY, checksum, 2))
            self.assertEqual((fact['source_available_at'], fact['stock_id']), (RECEIVED, 'TW:1000'))
            self.assertEqual(fact['available_at'], fact['recorded_at'])
            self.assertEqual(fact['source']['url'], CATALOG)
        with sqlite3.connect(self.runs/bundle.report['run']/'graph.db') as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM chip_metrics').fetchone(), (22,))
            self.assertEqual(conn.execute('SELECT stock_id FROM document_stocks').fetchall(), [('TW:1000',)])

    def test_full_file_inconsistencies_are_located_before_replacing_success(self):
        self.capture()
        self.normalize()
        before = self.output.read_bytes()
        for position, replacement, cause in [(5, -3, '買賣超'), (9, 1105, '外資及陸資'),
                                             (21, 6, '自營商'), (13, '--', '投信賣出股數'),
                                             (12, -2, '投信買進股數')]:
            with self.subTest(position=position):
                other = list(ROW)
                other[1], other[position] = '1001', replacement
                if position in (9, 21):  # Both sides shift, so the group net still balances.
                    other[position+1] += 1
                self.capture([ROW, other])
                with self.assertRaisesRegex(ValueError, 'row 3.*'+cause):
                    self.normalize()
                self.assertEqual(self.output.read_bytes(), before)

    def test_bad_receipts_schema_date_or_coverage_preserve_verified_output(self):
        self.capture()
        self.normalize()
        before = self.output.read_bytes()
        for case in ('checksum', 'mime', 'duplicate receipt', 'URL', 'timestamp', 'duplicate row',
                     'renamed column', 'missing column', 'other day', 'missing selection'):
            with self.subTest(case=case):
                self.capture()
                entries = json.loads(self.manifest.read_text())
                if case == 'checksum':
                    (self.raw/'11856.response').write_bytes(b'tampered')
                elif case == 'mime':
                    entries[0]['mime'] = 'text/html'
                elif case == 'duplicate receipt':
                    entries *= 2
                elif case == 'URL':
                    entries[0]['url'] = 'https://example.invalid'
                elif case == 'timestamp':
                    entries[0]['started_at'] = '2020-01-04T00:00:00+00:00'
                elif case == 'duplicate row':
                    self.capture([ROW, ROW])
                elif case == 'renamed column':
                    self.capture(fields=[*FIELDS[:-1], 'changed'])
                elif case == 'missing column':
                    self.capture([ROW[:-1]])
                elif case == 'other day':
                    self.capture([['1090101', *ROW[1:]]])
                else:
                    self.capture([[ROW[0], '1001', *ROW[2:]]])
                if case in ('mime', 'duplicate receipt', 'URL', 'timestamp'):
                    self.manifest.write_text(json.dumps(entries))
                with self.assertRaises(ValueError):
                    self.normalize()
                self.assertEqual(self.output.read_bytes(), before)

    def test_revisions_are_as_recorded_and_a_same_time_conflict_rolls_back(self):
        self.capture()
        self.normalize()
        first = self.research()
        self.normalize()
        repeated = self.research()
        self.assertFalse(repeated.report['registered_snapshot']['inserted'])
        self.assertEqual(repeated.facts['facts'], first.facts['facts'])

        pointer = (self.runs/'latest.json').read_bytes()
        self.output = self.root/'conflicting.json'
        self.capture([[*ROW[:-1], -4]])
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time'):
            self.research()
        self.assertEqual((self.runs/'latest.json').read_bytes(), pointer)
        with sqlite3.connect(self.root/'ledger.db') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM research_snapshots').fetchone(), (1,))

        self.output = self.root/'later.json'
        self.capture([[*ROW[:-1], -4]], received='2020-01-03T09:00:00+00:00')
        self.normalize()
        later = self.research()
        earlier = self.research(known_at=first.report['known_at'])
        def reported_total(bundle):
            return next(f for f in bundle.facts['facts'] if f['source_column'] == '三大法人買賣超股數合計')
        self.assertEqual((reported_total(earlier)['value'], reported_total(later)['value']), (-3, -4))
        self.assertEqual(earlier.facts, first.facts)
        self.assertEqual(reported_total(later)['id'], reported_total(first)['id'])
        self.assertNotEqual(reported_total(later)['raw_sha256'], reported_total(first)['raw_sha256'])
        with self.assertRaisesRegex(ValueError, 'no as-recorded stock coverage'):
            self.research(known_at=RECEIVED)

    def test_changed_capture_requires_its_own_normalized_file(self):
        self.capture()
        self.normalize()
        before = self.output.read_bytes()
        self.capture([[*ROW[:-1], -4]], received='2020-01-03T09:00:00+00:00')
        with self.assertRaisesRegex(ValueError, 'new output'):
            self.normalize()
        self.assertEqual(self.output.read_bytes(), before)
