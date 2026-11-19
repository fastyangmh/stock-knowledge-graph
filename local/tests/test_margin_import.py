"""Synthetic margin receipts through private normalization and as-recorded research."""
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

FIELDS = '資料日期 代號 名稱 前資餘額 資買 資賣 現償 資餘額 資屬證金 資使用率 資限額 前券餘額 券賣 券買 券償 券餘額 券屬證金 券使用率 券限額 資券相抵 備註'.split()
ROW = ['1090102', '1000', '合成公司', 100, 42, 12, 4, 126, 6, '12.6', 1000, 25, 7, 3, 0, 29, 2, '2.9', 1000, 1, 'X']
DAY = '2020-01-02'
RECEIVED = '2020-01-03T01:00:00+00:00'
URL = 'https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=data'


class MarginTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        self.manifest = self.raw/'manifest.json'
        self.out = self.root/'normalized.json'
        self.runs = self.root/'runs'

    def capture(self, rows=(ROW,), fields=FIELDS, observed=RECEIVED):
        stream = io.StringIO(newline='')
        csv.writer(stream).writerows([fields, *rows])
        body = stream.getvalue().encode('utf-8-sig')
        sha = hashlib.sha256(body).hexdigest()
        (self.raw/'11387.response').write_bytes(body)
        receipt = dict(id=11387, url=URL, catalog='https://data.gov.tw/dataset/11387', mime='application/csv',
                       started_at=observed, received_at=observed, status='200', exit=0, error='',
                       bytes=len(body), sha256=sha)
        self.manifest.write_text(json.dumps([receipt]))
        return sha

    def normalize(self, market='TPEX', day=DAY, symbol='1000'):
        from local.margin_import import main
        main(['--market', market, '--manifest', str(self.manifest), '--trade-date', day, '--symbols', symbol,
              '--output', str(self.out)])

    def research(self, **kwargs):
        report = run(self.out, ['1000'], history_db=self.root/'ledger.db', output_root=self.runs, **kwargs)
        return audit_bundle(self.runs, report['run'])

    def test_source_rows_preserve_side_flow_balance_unit_and_retrieval(self):
        sha = self.capture()
        self.normalize()
        bundle = self.research()
        facts = {f['metric']: f for f in bundle.facts['facts']}
        self.assertEqual(len(facts), 17)
        for metric, column, number, unit in (
            ('financing_buy', '資買', 42, 'source_reported'),
            ('short_sell', '券賣', 7, 'source_reported'),
            ('financing_balance', '資餘額', 126, 'source_reported'),
            ('short_repayment', '券償', 0, 'source_reported'),
            ('short_utilization', '券使用率', 2.9, 'percent'),
        ):
            f = facts['tpex_margin_'+metric]
            self.assertEqual((f['trade_date'], f['raw_sha256'], f['row_number'], f['source_column']), (DAY, sha, 2, column))
            self.assertEqual((f['value'], f['unit'], f['source_available_at']), (number, unit, RECEIVED))
            self.assertEqual(f['available_at'], f['recorded_at'])
            self.assertEqual(f['source']['market'], 'TPEX')
        with sqlite3.connect(self.runs/bundle.report['run']/'graph.db') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM chip_metrics').fetchone(), (17,))
            self.assertEqual(db.execute('SELECT stock_id FROM document_stocks').fetchall(), [('TW:1000',)])

    def test_partial_invalid_unselected_rows_or_unbound_listed_dates_preserve_success(self):
        self.capture()
        self.normalize()
        before = self.out.read_bytes()
        for position, bad_value, error in ((4, '', '資買'), (12, '--', '券賣'), (7, 125, '資餘額'),
                                           (15, 32, '券餘額'), (9, 'NaN', '資使用率'),
                                           (10, '-1', '資限額'), (0, '1090101', 'date')):
            with self.subTest(column=FIELDS[position]):
                other = list(ROW)
                other[1], other[position] = '1001', bad_value
                self.capture([ROW, other])
                with self.assertRaisesRegex(ValueError, 'row 3.*'+error):
                    self.normalize()
                self.assertEqual(self.out.read_bytes(), before)
        self.capture()
        with self.assertRaisesRegex(ValueError, '11680.*undated'):
            self.normalize(market='TWSE')
        self.assertEqual(self.out.read_bytes(), before)

    def test_utilization_keeps_reported_percent_and_rejects_a_changed_scale(self):
        self.capture()
        self.normalize()
        facts = self.research().facts['facts']
        self.assertEqual({f['source_column']: f['value'] for f in facts if f['unit'] == 'percent'},
                         {'資使用率': 12.6, '券使用率': 2.9})
        row = list(ROW)
        row[9] = '0.13'
        self.capture([row])
        self.out = self.root/'shifted.json'
        with self.assertRaisesRegex(ValueError, '資使用率'):
            self.normalize()
        self.assertFalse(self.out.exists())

    def test_revision_cutoff_and_conflict_leave_previous_research_available(self):
        sha = self.capture()
        self.normalize()
        first = self.research()
        self.normalize()
        self.assertEqual(self.research().facts['facts'], first.facts['facts'])
        latest = (self.runs/'latest.json').read_bytes()
        corrected = list(ROW)
        corrected[4], corrected[7], corrected[9] = 43, 127, '12.7'
        self.capture([corrected])
        with self.assertRaisesRegex(ValueError, 'new output'):
            self.normalize()
        self.out = self.root/'conflict.json'
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time'):
            self.research()
        self.assertEqual((self.runs/'latest.json').read_bytes(), latest)
        with sqlite3.connect(self.root/'ledger.db') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM research_snapshots').fetchone(), (1,))
        observed = '2020-01-03T04:00:00+00:00'
        revised_sha = self.capture([corrected], observed=observed)
        self.out = self.root/'revision.json'
        self.normalize()
        later = self.research()
        old = self.research(known_at=first.report['known_at'])
        for bundle, expected, checksum, received in ((old, 126, sha, RECEIVED), (later, 127, revised_sha, observed)):
            f = next(f for f in bundle.facts['facts'] if f['source_column'] == '資餘額')
            self.assertEqual((f['value'], f['raw_sha256'], f['source_available_at']), (expected, checksum, received))
        self.assertEqual(first.facts, old.facts)
        with self.assertRaisesRegex(ValueError, 'no as-recorded stock coverage'):
            self.research(known_at=observed)

    def test_unusable_capture_cannot_create_or_replace_research_input(self):
        self.capture()
        self.normalize()
        success = self.out.read_bytes()
        for case in ('bytes', 'header', 'width', 'duplicate', 'receipt date', 'absent stock', 'requested date'):
            with self.subTest(case=case):
                self.capture()
                if case == 'bytes':
                    (self.raw/'11387.response').write_bytes(b'wrong')
                elif case == 'header':
                    self.capture(fields=[*FIELDS[:-1], '詮釋未核對'])
                elif case == 'width':
                    self.capture(rows=[ROW[:-1]])
                elif case == 'duplicate':
                    self.capture(rows=[ROW, ROW])
                elif case == 'receipt date':
                    self.capture(observed='2020-01-01T00:00:00+00:00')
                elif case == 'absent stock':
                    self.capture(rows=[[ROW[0], '1001', *ROW[2:]]])
                with self.assertRaises(ValueError):
                    self.normalize(day='2020-01-03' if case == 'requested date' else DAY)
                self.assertEqual(self.out.read_bytes(), success)

    def test_full_receipt_conflict_rejected_even_on_disjoint_selection_and_old_cutoff(self):
        other = [ROW[0], '1001', *ROW[2:]]
        self.capture([ROW, other])
        self.normalize()
        first = self.research()
        self.out = self.root/'other.json'
        self.normalize(symbol='1001')
        self.research(known_at=first.report['known_at'])
        self.out = self.root/'different.json'
        self.capture([other])
        self.normalize(symbol='1001')
        with self.assertRaisesRegex(ValueError, 'conflicting same-time'):
            self.research(known_at=first.report['known_at'])

    def test_research_and_immutable_audit_check_chip_cells_against_receipt(self):
        from local.research_history import canonical
        self.capture()
        self.normalize()
        original = json.loads(self.out.read_bytes())
        bundle = self.research()
        for changes in [dict(value=987654, raw_sha256='0'*64), dict(value=987654),
                        dict(unit='lots'), dict(row_number=3), dict(source_column='unknown')]:
            with self.subTest(changes=changes):
                payload = json.loads(canonical(original))
                payload['chip_metrics'][-1].update(changes)
                self.out.write_bytes(canonical(payload))
                with self.assertRaises(ValueError):
                    self.research()
        folder = self.runs/bundle.report['run']
        facts_path = folder/'research-facts.json'
        facts = json.loads(facts_path.read_bytes())
        facts['facts'][-1]['value'] = 987654
        body = canonical(facts)
        facts_path.write_bytes(body)
        report = json.loads((folder/'report.json').read_bytes())
        report['research_facts'].update(sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body))
        (folder/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'chip'):
            audit_bundle(self.runs, bundle.report['run'])

    def test_later_source_row_keeps_master_stock_identity_and_attribution(self):
        master = dict(stock_id='TW:1000', ticker='1000', market='TW', name='甲公司全名', industry='01',
                      source_id='master', source_url='https://example.invalid/master', attribution='主檔署名')
        self.out.write_text(json.dumps(dict(stocks=[master], sources=[], documents=[], chip_metrics=[],
                                       financial_metrics=[], metadata=dict(observed_at='2019-12-31T00:00:00Z'))))
        first = self.research()
        self.out = self.root/'latest-input.json'
        self.capture([ROW])
        self.normalize()
        for bundle in (self.research(), self.research(known_at=first.report['known_at'])):
            node, = [n for n in bundle.graphs['TW:1000']['nodes'] if n['type'] == 'stock']
            self.assertEqual((node['label'], node['industry'], node['source_url'], node['attribution']),
                             ('甲公司全名', '01', master['source_url'], '主檔署名'))

    def test_audit_detects_missing_chip_cell_even_when_counts_and_file_hashes_agree(self):
        from local.research_history import canonical
        self.capture()
        self.normalize()
        bundle = self.research()
        folder = self.runs/bundle.report['run']
        facts_path = folder/'research-facts.json'
        facts = json.loads(facts_path.read_bytes())
        facts['facts'].pop()
        facts['coverage']['TW:1000']['chip_metric'] -= 1
        body = canonical(facts)
        facts_path.write_bytes(body)
        report = json.loads((folder/'report.json').read_bytes())
        report['research_facts'].update(sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body), count=16)
        report['quality']['counts']['chip_metrics'] = 16
        (folder/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'chip'):
            audit_bundle(self.runs, bundle.report['run'])
