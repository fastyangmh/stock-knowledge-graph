"""Offline official industry and news receipts through private research and audit."""
import csv
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from local.bundle_audit import audit_bundle
from local.research import run

FIELDS = '出表日期 年度 季別 公司代號 公司名稱 產業別 基本每股盈餘(元) 普通股每股面額 營業收入 營業利益 營業外收入及支出 稅後淨利'.split()
ROW = ['1091105', '109', '3', '1000', '合成甲', '測試業', '12', '10元', '100', '20', '3', '18']
TIME = '2020-11-05T08:00:00+00:00'
URLS = {
    20756: 'https://mopsfin.twse.com.tw/opendata/t187ap14_L.csv',
    20757: 'https://mopsfin.twse.com.tw/opendata/t187ap14_O.csv',
    11546: 'https://www.twse.com.tw/news/newsList?response=open_data',
    6040: 'https://www.fsc.gov.tw/RSS/Messages?language=chinese&serno=201202290009',
}


def csv_body(fields, rows):
    buf = io.StringIO(newline='')
    csv.writer(buf).writerows([fields, *rows])
    return buf.getvalue().encode('utf-8-sig')


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.raw = self.root/'raw'
        self.raw.mkdir()
        self.manifest = self.raw/'manifest.json'
        self.output = self.root/'normalized.json'
        self.runs = self.root/'runs'

    def capture(self, ident, body, *, observed=TIME, mime='text/csv'):
        sha = hashlib.sha256(body).hexdigest()
        row = dict(id=ident, catalog=f'https://data.gov.tw/dataset/{ident}', url=URLS[ident],
                   mime=mime, status='200', exit=0, error='', started_at=observed,
                   received_at=observed, bytes=len(body), sha256=sha)
        self.manifest.write_text(json.dumps([row]))
        (self.raw/f'{ident}.response').write_bytes(body)
        return sha

    def normalize(self, ident):
        from local.news_industry import main
        main(['--dataset', str(ident), '--manifest', str(self.manifest), '--output', str(self.output)])
        return json.loads(self.output.read_bytes())

    def research(self, **kwargs):
        report = run(self.output, ['1000'], history_db=self.root/'ledger.db', output_root=self.runs, **kwargs)
        return audit_bundle(self.runs, report['run'])

    def test_industry_documents_preserve_all_company_relations_and_period(self):
        other = [*ROW[:3], '1001', '合成乙', '乙業', *ROW[6:]]
        sha = self.capture(20756, csv_body(FIELDS, [ROW, other]))
        payload = self.normalize(20756)
        self.assertEqual([s['stock_id'] for s in payload['stocks']], ['TW:1000', 'TW:1001'])
        doc = payload['documents'][0]
        self.assertEqual((doc['stock_ids'], doc['period_end'], doc['source_report_date']),
                         (['TW:1000'], '2020-09-30', '2020-11-05'))
        self.assertEqual((doc['industry'], doc['relation_basis'], doc['raw_sha256'], doc['row_number']),
                         ('測試業', 'source_reported_industry', sha, 2))
        bundle = self.research()
        self.assertFalse(bundle.facts['facts'])
        self.assertEqual(bundle.report['quality']['counts']['documents'], 1)
        graph = bundle.graphs['TW:1000']
        self.assertIn('測試業', json.dumps(graph, ensure_ascii=False))
        stock = next(n for n in graph['nodes'] if n['type'] == 'stock')
        self.assertEqual((stock['raw_sha256'], stock['row_number'], stock['source_column']), (sha, 2, '公司代號'))
        self.assertEqual(stock['source_url'], 'https://data.gov.tw/dataset/20756')
        self.assertTrue(stock['license_url'] and stock['attribution'])

    def test_unlinked_news_replays_as_a_private_index_separate_from_stock_evidence(self):
        self.capture(20757, csv_body(FIELDS, [ROW]))
        self.normalize(20757)
        first = self.research()
        self.output = self.root/'index.json'
        fields = ['標題', '連結', '日期']
        a = 'https://www.twse.com.tw/zh/about/news/news/content.html?a'
        b = a[:-1]+'b'
        sha = self.capture(11546, csv_body(fields, [['TW:1000 合成同名', a, '1091104'],
                                                  ['TW:1000 合成同名', b, '1091105']]))
        index = self.normalize(11546)
        self.assertEqual((index['stocks'], index['documents']), ([], []))
        bundle = self.research()
        evidence, = bundle.report['quality']['news_indexes']
        self.assertEqual(evidence['source_id'], 'twse_news_11546')
        self.assertEqual(evidence['raw_sha256'], sha)
        self.assertEqual([(x['external_id'], x['published_date'], x['row_number']) for x in evidence['articles']],
                         [(a, '2020-11-04', 2), (b, '2020-11-05', 3)])
        self.assertNotIn('合成同名', json.dumps(bundle.graphs, ensure_ascii=False))
        self.assertNotIn('news_indexes', self.research(known_at=first.report['known_at']).report['quality'])

    def test_rss_guid_is_stable_and_description_stays_in_original(self):
        base = 'https://www.fsc.gov.tw/ch/home.jsp?id='
        def item(key, description):
            return (f'<item><title>合成新聞</title><pubDate>Thu, 05 Nov 2020 00:00:00 GMT</pubDate>'
                    f'<link>{base}landing</link><guid isPermaLink="true">{base}{key}</guid>'
                    f'{description}<category domain="theme">540</category></item>')
        xml = ('<rss version="2.0"><channel><title>合成新聞</title><link>https://www.fsc.gov.tw</link>'
               '<description>索引</description>'+item('1', '<description>&lt;p&gt;私人段落&lt;/p&gt;</description>')
               +item('2', '')+'</channel></rss>').encode()
        self.capture(6040, xml, mime='text/xml; charset=utf-8')
        payload = self.normalize(6040)
        self.assertEqual([(x['external_id'], x['has_description']) for x in payload['articles']],
                         [(base+'1', True), (base+'2', False)])
        self.assertEqual(payload['articles'][0]['published_at'], '2020-11-05T00:00:00+00:00')
        self.assertNotIn('私人段落', self.output.read_text())

    def test_changed_retrieval_same_time_is_atomic_and_later_revision_replays(self):
        self.capture(20756, csv_body(FIELDS, [ROW]))
        self.normalize(20756)
        self.research()
        self.output = self.root/'news-first.json'
        link = 'https://www.twse.com.tw/zh/about/news/news/content.html?a'
        def save(title, observed):
            self.capture(11546, csv_body(['標題', '連結', '日期'], [[title, link, '1091105']]), observed=observed)
            return self.normalize(11546)
        save('初版', TIME)
        initial = self.research()
        latest = (self.runs/'latest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'new output'):
            save('修訂', TIME)
        self.output = self.root/'news-conflict.json'
        save('修訂', TIME)
        with self.assertRaisesRegex(ValueError, 'same-time'):
            self.research()
        self.assertEqual((self.runs/'latest.json').read_bytes(), latest)
        self.output = self.root/'news-later.json'
        save('修訂', '2020-11-06T08:00:00+00:00')
        later = self.research()
        old = self.research(known_at=initial.report['known_at'])
        for bundle, title in ((old, '初版'), (later, '修訂')):
            entry, = bundle.report['quality']['news_indexes'][0]['articles']
            self.assertEqual((entry['external_id'], entry['title']), (link, title))
        self.assertEqual(initial.report['quality'], old.report['quality'])

    def test_audit_binds_unlinked_index_to_archived_observation(self):
        self.capture(20756, csv_body(FIELDS, [ROW]))
        self.normalize(20756)
        self.research()
        self.output = self.root/'news.json'
        self.capture(11546, csv_body(['標題', '連結', '日期'], [['合成原題', 'https://www.twse.com.tw/example', '1091105']]))
        self.normalize(11546)
        bundle = self.research()
        path = self.runs/bundle.report['run']/'report.json'
        report = json.loads(path.read_bytes())
        report['quality']['news_indexes'][0]['articles'][0]['title'] = '未經保存的標題'
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'news_index'):
            audit_bundle(self.runs, bundle.report['run'])

    def test_each_source_declares_text_and_derivative_scope_in_bundle(self):
        self.capture(20756, csv_body(FIELDS, [ROW]))
        self.normalize(20756)
        first = self.research()
        node, = [n for n in first.graphs['TW:1000']['nodes'] if n['type'] == 'industry_report']
        self.assertEqual((node['industry'], node['relation_basis'], node['source_column'], node['row_number']),
                         ('測試業', 'source_reported_industry', '產業別', 2))
        scopes = first.report['quality']['snapshots'][0]['sources'][0]['permitted_use']
        self.assertEqual(scopes['embedding'], 'private_company_industry_fields')
        self.assertEqual(scopes['public_display'], 'unreviewed')
        self.output = self.root/'news.json'
        self.capture(11546, csv_body(['標題', '連結', '日期'], [['索引', 'https://www.twse.com.tw/test', '1091105']]))
        self.normalize(11546)
        second = self.research()
        news_source, = [src for s in second.report['quality']['snapshots'] for src in s['sources']
                        if src['source_id'] == 'twse_news_11546']
        self.assertEqual(news_source['permitted_use'], dict(index='private_title_link_date', full_text='unreviewed',
                         summary='unreviewed', embedding='unreviewed', public_display='unreviewed'))

    def test_invalid_source_rows_and_receipts_keep_previous_output(self):
        self.capture(20757, csv_body(FIELDS, [ROW]))
        self.normalize(20757)
        success = self.output.read_bytes()
        for body in [csv_body(FIELDS, [ROW, ROW]), csv_body(FIELDS[:-1], [ROW[:-1]]),
                     csv_body(FIELDS, [[*ROW[:5], '--', *ROW[6:]]]),
                     csv_body(FIELDS, [[*ROW[:2], '4', *ROW[3:]]]),
                     csv_body(FIELDS, [ROW[:-1]]), csv_body(FIELDS, [])]:
            with self.subTest(body=body):
                self.capture(20757, body)
                with self.assertRaisesRegex(ValueError, 'row |header|empty'):
                    self.normalize(20757)
                self.assertEqual(self.output.read_bytes(), success)
        fields = ['標題', '連結', '日期']
        good = ['合成標題', 'https://www.twse.com.tw/example', '1091105']
        for rows in [[good, good], [[good[0], 'javascript:alert(1)', good[2]]],
                     [[good[0], 'https://www.twse.com.tw.attacker.invalid/example', good[2]]],
                     [[good[0], good[1], '2020-11-05']], [['', *good[1:]]]]:
            with self.subTest(rows=rows):
                self.capture(11546, csv_body(fields, rows))
                with self.assertRaisesRegex(ValueError, 'article|date'):
                    self.normalize(11546)
                self.assertEqual(self.output.read_bytes(), success)
        for xml in [b'<rdf>unsupported</rdf>', b'<rss version="2.0"><channel></rss>',
                    b'<!DOCTYPE x><rss version="2.0"><channel/></rss>']:
            with self.subTest(xml=xml):
                self.capture(6040, xml, mime='text/xml')
                with self.assertRaisesRegex(ValueError, 'RSS'):
                    self.normalize(6040)
                self.assertEqual(self.output.read_bytes(), success)
        self.capture(11546, csv_body(fields, [good]))
        (self.raw/'11546.response').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.normalize(11546)
        self.capture(11546, csv_body(fields, [good]), mime='text/xml')
        with self.assertRaisesRegex(ValueError, 'MIME'):
            self.normalize(11546)
        self.capture(6040, b'<rss/>', mime='text/xml')
        receipt = json.loads(self.manifest.read_bytes())
        receipt[0]['url'] += '&redirect=1'
        self.manifest.write_text(json.dumps(receipt))
        with self.assertRaisesRegex(ValueError, 'receipt'):
            self.normalize(6040)
        self.assertEqual(self.output.read_bytes(), success)

    def test_later_classification_preserves_earlier_quarter_and_conflicting_raw_rejected(self):
        sha = self.capture(20757, csv_body(FIELDS, [ROW]))
        first_input = self.normalize(20757)
        first = self.research()
        pointer = (self.runs/'latest.json').read_bytes()
        self.output = self.root/'changed.json'
        corrected = [*ROW[:5], '修訂分類', *ROW[6:]]
        self.capture(20757, csv_body(FIELDS, [corrected]))
        self.normalize(20757)
        with self.assertRaisesRegex(ValueError, 'same-time'):
            self.research()
        self.assertEqual((self.runs/'latest.json').read_bytes(), pointer)
        self.output = self.root/'later.json'
        revised = self.capture(20757, csv_body(FIELDS, [corrected]), observed='2020-11-06T00:00:00+00:00')
        later_input = self.normalize(20757)
        self.assertEqual(first_input['documents'][0]['document_id'], later_input['documents'][0]['document_id'])
        later = self.research()
        old = self.research(known_at=first.report['known_at'])
        for bundle, sector, checksum in ((old, '測試業', sha), (later, '修訂分類', revised)):
            [doc] = [n for n in bundle.graphs['TW:1000']['nodes'] if n['type'] == 'industry_report']
            self.assertEqual((doc['industry'], doc['raw_sha256'], doc['period_end']), (sector, checksum, '2020-09-30'))

    def test_company_master_identity_survives_a_later_industry_report(self):
        self.output.write_text(json.dumps(dict(
            stocks=[dict(stock_id='TW:1000', ticker='1000', market='TW', name='主檔公司名', industry='01')],
            documents=[], sources=[], chip_metrics=[], financial_metrics=[],
            metadata=dict(observed_at='2020-11-01T00:00:00+00:00'))))
        self.research()
        self.output = self.root/'sector.json'
        self.capture(20757, csv_body(FIELDS, [ROW]))
        self.normalize(20757)
        graph = self.research().graphs['TW:1000']
        stock, = [n for n in graph['nodes'] if n['type'] == 'stock']
        self.assertEqual((stock['label'], stock['industry']), ('主檔公司名', '01'))
        self.assertIn('合成甲', next(n['label'] for n in graph['nodes'] if n['type'] == 'industry_report'))
