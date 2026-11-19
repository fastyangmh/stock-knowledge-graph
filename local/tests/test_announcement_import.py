"""Official announcement rows through the private import, research and bundle audit interfaces."""
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

FIELDS = ['出表日期', '發言日期', '發言時間', '公司代號', '公司名稱', '主旨', '符合條款', '事實發生日', '說明']
BODY = '第一行,「合成」\r\n<script>fake()</script> javascript:test() 乙公司(2000)'
ROW = ['1090103', '1090102', '70501', '1000', '甲公司', '<img src=x>合成公告', '第20款', '1090201', BODY]
RECEIVED = '2020-01-03T01:00:00+00:00'


class AnnouncementTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        self.manifest = self.raw/'manifest.json'
        self.output = self.root/'out.json'
        self.runs = self.root/'runs'
        self.dataset = 18418

    def capture(self, rows, header=FIELDS, received=RECEIVED):
        data = io.StringIO(newline='')
        csv.writer(data).writerows([header, *rows])
        body = data.getvalue().encode('utf-8-sig')
        sha = hashlib.sha256(body).hexdigest()
        filename = 't187ap04_' + ('O' if self.dataset == 18418 else 'L') + '.csv'
        (self.raw/f'{self.dataset}.response').write_bytes(body)
        entry = dict(id=self.dataset, catalog=f'https://data.gov.tw/dataset/{self.dataset}',
                     url='https://mopsfin.twse.com.tw/opendata/'+filename, status='200', exit=0, error='',
                     mime='text/csv', started_at=received, received_at=received, bytes=len(body), sha256=sha)
        self.manifest.write_text(json.dumps([entry]))
        return sha

    def normalize(self, *extra):
        from local.announcement_import import main
        main(['--dataset', str(self.dataset), '--manifest', str(self.manifest), '--output', str(self.output), *extra])
        return json.loads(self.output.read_bytes())

    def research(self, symbols=('1000',), **kwargs):
        result = run(self.output, list(symbols), history_db=self.root/'ledger.db', output_root=self.runs, **kwargs)
        return audit_bundle(self.runs, result['run'])

    def test_duplicate_quoted_plain_text_has_one_source_scoped_identity_and_no_numeric_facts(self):
        sha = self.capture([ROW, ROW])
        payload = self.normalize()
        doc, = payload['documents']
        self.assertEqual(doc['content'], BODY)
        self.assertEqual(doc['stock_ids'], ['TW:1000'])
        self.assertEqual(doc['published_at'], '2020-01-02T07:05:01+08:00')
        self.assertEqual(doc['available_at'], RECEIVED)
        locator, = payload['metadata']['records']
        self.assertEqual((locator['csv_records'], locator['event_date'], locator['clause']),
                         ([2, 3], '2020-02-01', '第20款'))
        self.assertEqual(payload['metadata']['source_snapshots'][0]['sha256'], sha)
        bundle = self.research()
        self.assertFalse(bundle.facts['facts'])
        with sqlite3.connect(self.runs/bundle.report['run']/'graph.db') as db:
            self.assertEqual(db.execute('SELECT document_id, title, content FROM documents').fetchall(),
                             [(doc['document_id'], ROW[5], BODY)])
        self.assertEqual(self.normalize(), payload)
        self.assertFalse(self.research().report['registered_snapshot']['inserted'])
        with self.assertRaisesRegex(ValueError, 'no as-recorded stock coverage'):
            self.research(known_at=RECEIVED)


    def review(self, sha, record, **fields):
        p = self.root/'review.json'
        p.write_text(json.dumps(dict(raw_sha256=sha, record=record, **fields)))
        return ['--record', str(record), '--review', str(p)]

    def test_only_explicit_evidenced_company_links_share_a_single_document(self):
        sha = self.capture([ROW, [*ROW[:2], '123400', *ROW[3:]]])
        link = dict(ticker='2000', name='乙公司', evidence='乙公司(2000)')
        payload = self.normalize(*self.review(sha, 2, links=[link]))
        self.assertEqual([d['stock_ids'] for d in payload['documents']], [['TW:1000', 'TW:2000']])
        self.assertEqual(payload['metadata']['records'][0]['reviewed_links'], [link])
        bundle = self.research(['1000', '2000'])
        did = payload['documents'][0]['document_id']
        for graph in bundle.graphs.values():
            self.assertIn('doc:'+did, [node['id'] for node in graph['nodes']])
        before = self.output.read_bytes()
        for invalid in [dict(link, evidence='不存在'), dict(link, ticker='2001'), dict(link, name='別家公司')]:
            with self.assertRaisesRegex(ValueError, 'link'):
                self.normalize(*self.review(sha, 2, links=[invalid]))
            self.assertEqual(self.output.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'review'):
            self.normalize(*self.review('0'*64, 2, links=[link]))


    def test_reviewed_correction_and_withdrawal_follow_original_id_and_replay_cutoffs(self):
        rows = [ROW, [*ROW[:2], '121000', *ROW[3:5], '更正原公告', *ROW[6:]],
                [*ROW[:2], '160000', *ROW[3:5], '撤回同日公告', *ROW[6:]]]
        sha = self.capture(rows)
        original = self.normalize(*self.review(sha, 2, links=[dict(ticker='2000', name='乙公司', evidence='乙公司(2000)')]))
        first = self.research()
        did = original['documents'][0]['document_id']
        previous, parent = first, self.output
        for index, action, title in [(3, 'correct', '更正原公告'), (4, 'withdraw', '撤回同日公告')]:
            self.output = self.root/f'{action}.json'
            revision = dict(action=action, target_document_id=did, evidence=title,
                            target_snapshot_sha256=previous.report['registered_snapshot']['sha256'])
            self.normalize(*self.review(sha, index, revision=revision), '--parent', str(parent))
            previous = self.research(['2000'], enable_source_revisions=True)
            parent = self.output
            docs = [n for n in previous.graphs['TW:2000']['nodes'] if n['id'].startswith('doc:')]
            self.assertEqual([(n['id'], n['label']) for n in docs], [('doc:'+did, title)] if action=='correct' else [])
            self.assertEqual(previous.report['quality']['source_revisions'][-1]['notice']['action'], action)
            self.assertFalse(self.research().report['registered_snapshot']['inserted'])
        early = self.research(known_at=first.report['known_at'])
        self.assertIn(ROW[5], [n['label'] for n in early.graphs['TW:1000']['nodes']])
        self.assertEqual(audit_bundle(self.runs, first.report['run']).report_sha256, first.report_sha256)


    def test_company_name_in_announcement_can_be_resolved_by_explicit_company_record(self):
        named_only = [*ROW[:-1], '1.證券名稱:\r\n乙公司 普通股']
        corroborating = [*ROW[:3], '2000', '乙公司', *ROW[5:]]
        sha = self.capture([named_only, corroborating])
        link = dict(ticker='2000', name='乙公司', evidence='乙公司 普通股', company_record=3)
        payload = self.normalize(*self.review(sha, 2, links=[link]))
        self.assertEqual(payload['documents'][0]['stock_ids'], ['TW:1000', 'TW:2000'])
        audited = self.research(['1000', '2000'])
        for ticker, row in [('1000', 2), ('2000', 3)]:
            stock = next(n for n in audited.graphs['TW:'+ticker]['nodes'] if n['id'] == 'stock:TW:'+ticker)
            self.assertEqual((stock['source_id'], stock['raw_sha256'], stock['row_number'], stock['source_column']),
                             ('tpex-mops-18418', sha, row, '公司代號'))
            self.assertEqual(stock['source_url'], 'https://data.gov.tw/dataset/18418')
            self.assertTrue(stock['attribution'] and stock['license_url'])
        with self.assertRaisesRegex(ValueError, 'company record'):
            self.normalize(*self.review(sha, 2, links=[dict(link, company_record=2)]))


    def test_schema_drift_receipt_damage_and_collisions_leave_the_last_success_replayable(self):
        self.capture([ROW])
        self.normalize()
        original = self.research()
        before, latest = self.output.read_bytes(), (self.runs/'latest.json').read_bytes()
        for label, fields, rows in [
            ('column change', [*FIELDS[:-1], 'other'], [ROW]), ('missing value', FIELDS, [[*ROW[:-1], '']]),
            ('bad day', FIELDS, [[*ROW[:7], '1090231', ROW[8]]]), ('bad time', FIELDS, [[*ROW[:2], '297501', *ROW[3:]]]),
            ('future publication', FIELDS, [[ROW[0], '1090104', *ROW[2:]]]),
            ('unselected same-time conflict', FIELDS, [ROW, [*ROW[:-1], 'another text']]),
            ('bytes mismatch', FIELDS, [ROW]), ('changed normalized output', FIELDS, [[*ROW[:-1], 'changed']])]:
            with self.subTest(label=label):
                self.capture(rows, fields)
                if label == 'bytes mismatch':
                    (self.raw/'18418.response').write_bytes(b'tampered')
                with self.assertRaises(ValueError):
                    self.normalize('--record', '2')
                self.assertEqual(self.output.read_bytes(), before)
        self.output = self.root/'conflict.json'
        self.capture([[*ROW[:-1], 'different same timestamp']])
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time'):
            self.research()
        self.assertEqual((self.runs/'latest.json').read_bytes(), latest)
        self.assertEqual(audit_bundle(self.runs, original.report['run']).report_sha256, original.report_sha256)

    def test_two_publishers_repeating_the_same_text_have_two_traceable_documents(self):
        for dataset in (18418, 18415):
            self.dataset = dataset
            self.capture([ROW])
            self.output = self.root/f'{dataset}.json'
            self.normalize()
            self.research()
        repeated = self.research()
        self.assertFalse(repeated.report['registered_snapshot']['inserted'])
        nodes = [n for n in repeated.graphs['TW:1000']['nodes'] if n['id'].startswith('doc:')]
        self.assertEqual({n['id'] for n in nodes}, {'doc:tpex:18418:1000:1090102:070501',
                                                    'doc:twse:18415:1000:1090102:070501'})

    def test_disjoint_announcement_selections_conflict_by_full_receipt(self):
        other = [*ROW[:3], '2000', '乙公司', *ROW[5:]]
        self.capture([ROW, other])
        self.normalize('--record', '2')
        first = self.research()
        self.output = self.root/'other.json'
        self.normalize('--record', '3')
        self.research(known_at=first.report['known_at'])
        self.output = self.root/'changed.json'
        self.capture([other])
        self.normalize()
        with self.assertRaisesRegex(ValueError, 'conflicting same-time'):
            self.research(known_at=first.report['known_at'])

    def test_unreviewed_refresh_preserves_reviewed_links_and_parent_for_withdrawal(self):
        rows = [ROW, [*ROW[:2], '121000', *ROW[3:5], '撤回原公告', *ROW[6:]]]
        sha = self.capture(rows)
        link = dict(ticker='2000', name='乙公司', evidence='乙公司(2000)')
        parent = self.output
        payload = self.normalize(*self.review(sha, 2, links=[link]))
        first = self.research(['2000'])
        self.output = self.root/'batch.json'
        self.capture(rows, received='2020-01-04T01:00:00+00:00')
        self.normalize()
        refreshed = self.research(['2000'])
        did = 'doc:'+payload['documents'][0]['document_id']
        def node(bundle):
            return next(n for n in bundle.graphs['TW:2000']['nodes'] if n['id'] == did)
        self.assertEqual(node(refreshed), node(first))
        self.output = self.root/'withdraw.json'
        revision = dict(action='withdraw', target_document_id=did[4:], evidence='撤回原公告',
                        target_snapshot_sha256=first.report['registered_snapshot']['sha256'])
        self.normalize(*self.review(sha, 3, revision=revision), '--parent', str(parent))
        withdrawn = self.research(['2000'], enable_source_revisions=True)
        self.assertNotIn(did, [n['id'] for n in withdrawn.graphs['TW:2000']['nodes']])
        self.assertEqual(node(self.research(['2000'], known_at=first.report['known_at'])), node(first))

    def test_later_source_row_keeps_master_stock_identity_and_attribution(self):
        master = dict(stock_id='TW:1000', ticker='1000', market='TW', name='甲公司全名', industry='01',
                      source_id='master', source_url='https://example.invalid/master', attribution='主檔署名')
        self.output.write_text(json.dumps(dict(stocks=[master], sources=[], documents=[], chip_metrics=[],
                                       financial_metrics=[], metadata=dict(observed_at='2019-12-31T00:00:00Z'))))
        first = self.research()
        self.output = self.root/'latest-input.json'
        self.capture([ROW])
        self.normalize()
        for bundle in (self.research(), self.research(known_at=first.report['known_at'])):
            node, = [n for n in bundle.graphs['TW:1000']['nodes'] if n['type'] == 'stock']
            self.assertEqual((node['label'], node['industry'], node['source_url'], node['attribution']),
                             ('甲公司全名', '01', master['source_url'], '主檔署名'))

    def test_company_mentioned_by_name_without_review_cannot_gain_a_link_during_research(self):
        other = [*ROW[:3], '2000', '乙公司', *ROW[5:]]
        self.capture([[*ROW[:-1], '乙公司 普通股'], other])
        payload = self.normalize()
        payload['documents'][0]['stock_ids'].append('TW:2000')
        self.output.write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, 'reviewed links'):
            self.research(['2000'])
