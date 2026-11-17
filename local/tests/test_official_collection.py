"""Synthetic HTTP boundary; real private files, SQLite, research and audit."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local.collect_official import main as collect_main
from local.core import ROOT

WHEN = '2026-11-15T08:00:00+00:00'
COMPANY = ('出表日期,公司代號,公司名稱\n'
           '1151115,2330,Synthetic A\n1151115,2454,Synthetic B\n').encode()
REVENUE = ('出表日期,資料年月,公司代號,公司名稱,營業收入-當月營收\n'
           '1151115,11510,2330,Synthetic A,1000\n'
           '1151115,11510,2454,Synthetic B,2000\n').encode()


class Response(io.BytesIO):
    def __init__(self, body, url, content_type='text/csv; charset=utf-8'):
        super().__init__(body)
        self.url = url
        self.status = 200
        self.headers = {} if content_type is None else {'Content-Type': content_type}

    def geturl(self):
        return self.url


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = ROOT / 'local/official_datasets.json'
        self.sources = [s for s in json.loads(self.registry.read_text()) if s['enabled']]

    def collect(self, bodies=(COMPANY, REVENUE), content_type='text/csv; charset=utf-8', extra=()):
        responses = [Response(body, source['resource_url'], content_type)
                     for body, source in zip(bodies, self.sources)]
        with patch('local.collect_official.build_opener') as build, \
             patch('local.collect_official.now', return_value=WHEN), \
             patch('local.collect_official.time.sleep'), redirect_stdout(io.StringIO()):
            build.return_value.open.side_effect = responses
            collect_main(['--registry', str(self.registry), '--output-dir', str(self.root/'snapshots'), *extra])
        return json.loads((self.root/'snapshots/retrieval_manifest.json').read_text())

    def test_cli_preserves_http_evidence_with_actual_bytes(self):
        manifest = self.collect()
        company = manifest['datasets'][0]
        self.assertEqual(company['http_status'], 200)
        self.assertEqual(company['content_type'], 'text/csv; charset=utf-8')
        self.assertEqual(company['response_url'], self.sources[0]['resource_url'])
        self.assertEqual(company['retrieved_at'], WHEN)
        self.assertEqual((self.root/'snapshots'/company['path']).read_bytes(), COMPANY)
        self.assertEqual(company['bytes'], len(COMPANY))

    def test_second_source_http_failure_preserves_success_and_bounded_evidence(self):
        from urllib.error import HTTPError
        self.collect()
        previous = (self.root/'snapshots/retrieval_manifest.json').read_bytes()
        denied = b'<html>forbidden</html>'
        error = HTTPError(self.sources[1]['resource_url'], 403, 'forbidden',
                          {'Content-Type': 'text/html'}, io.BytesIO(denied))
        with patch('local.collect_official.build_opener') as build, \
             patch('local.collect_official.now', return_value=WHEN), \
             patch('local.collect_official.time.sleep'):
            build.return_value.open.side_effect = [Response(COMPANY, self.sources[0]['resource_url']), error]
            with self.assertRaises(HTTPError):
                collect_main(['--registry', str(self.registry), '--output-dir', str(self.root/'snapshots')])
        self.assertEqual((self.root/'snapshots/retrieval_manifest.json').read_bytes(), previous)
        reports = list((self.root/'snapshots').glob('retrieval-failure-*.json'))
        self.assertEqual(len(reports), 1)
        report = json.loads(reports[0].read_text())
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['failure']['dataset_id'], 'twse_monthly_revenue')
        self.assertEqual(report['failure']['http_status'], 403)
        self.assertEqual(report['failure']['error_category'], 'http_error')
        self.assertEqual(report['failure']['content_type'], 'text/html')
        self.assertFalse(report['failure']['body_truncated'])
        self.assertEqual((self.root/'snapshots'/report['failure']['path']).read_bytes(), denied)

    def test_html_and_oversize_failures_never_become_financial_snapshots(self):
        cases = [(b'<html>denied</html>', (), False, 'csv_validation'),
                 (b'a,b\n1,2\n' * 20, ('--max-bytes', '24'), True, 'response_size')]
        for body, extra, truncated, category in cases:
            with self.subTest(category=category):
                before = set((self.root/'snapshots').glob('retrieval-failure-*.json'))
                with self.assertRaises(ValueError):
                    self.collect(bodies=(body,), extra=extra)
                reports = set((self.root/'snapshots').glob('retrieval-failure-*.json')) - before
                self.assertEqual(len(reports), 1)
                failure = json.loads(reports.pop().read_text())['failure']
                self.assertEqual(failure['error_category'], category)
                self.assertEqual(failure['http_status'], 200)
                self.assertEqual(failure['body_truncated'], truncated)
                self.assertIsNotNone(failure['captured_sha256'])
                self.assertEqual(failure['sha256'] is None, truncated)
                self.assertEqual((self.root/'snapshots'/failure['path']).read_bytes(), body[:24] if truncated else body)
                self.assertFalse((self.root/'snapshots/retrieval_manifest.json').exists())

    def test_full_file_profile_and_two_symbol_cli_research_audit(self):
        from local.official_import import main as import_main
        from local.research import main as research_main
        from local.bundle_audit import main as audit_main
        company = COMPANY + '1151115,9999,Unselected\n'.encode()
        revenue = REVENUE + '1151115,11510,9999,Unselected,not-selected-number\n'.encode()
        manifest = self.collect((company, revenue), extra=('--symbols', '2330', '2454'))
        profile = manifest['datasets'][1]['profile']
        self.assertEqual(profile['row_count'], 3)
        self.assertEqual(profile['headers'], ['出表日期', '資料年月', '公司代號', '公司名稱', '營業收入-當月營收'])
        self.assertEqual(profile['report_dates'], {'2026-11-15': 3})
        self.assertEqual(profile['revenue_months'], {'2026-10': 3})
        self.assertEqual(profile['selection']['present'], ['TW:2330', 'TW:2454'])
        self.assertEqual(profile['selection']['missing'], [])
        self.assertEqual(manifest['selected_value_validation'], 'passed')
        with redirect_stdout(io.StringIO()):
            import_main(['--snapshot-dir', str(self.root/'snapshots'), '--symbols', '2330', '2454',
                         '--as-of', '2026-11-15', '--output', str(self.root/'input.json')])
            research_main(['--input', str(self.root/'input.json'), '--symbols', '2330', '2454',
                           '--analysis', 'none', '--history-db', str(self.root/'history.db'),
                           '--output-root', str(self.root/'runs')])
            self.assertEqual(audit_main(['--root', str(self.root/'runs')]), 0)
        pointer = json.loads((self.root/'runs/latest.json').read_text())
        self.assertTrue((self.root/'runs'/pointer['run']/'graph.db').is_file())
        normalized = json.loads((self.root/'input.json').read_text())
        self.assertEqual([m['value'] for m in normalized['financial_metrics']], [1000, 2000])
        self.assertEqual([m['unit'] for m in normalized['financial_metrics']], ['source_reported']*2)
        latest = (self.root/'runs/latest.json').read_bytes()
        manifest_before = (self.root/'snapshots/retrieval_manifest.json').read_bytes()
        database = self.root/'runs'/pointer['run']/'graph.db'
        database_before = database.read_bytes()
        with self.assertRaises(ValueError):
            self.collect((company, b'<html>synthetic denial</html>'), extra=('--symbols', '2330', '2454'))
        self.assertEqual((self.root/'snapshots/retrieval_manifest.json').read_bytes(), manifest_before)
        self.assertEqual((self.root/'runs/latest.json').read_bytes(), latest)
        self.assertEqual(database.read_bytes(), database_before)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(audit_main(['--root', str(self.root/'runs')]), 0)


    def test_unselected_date_anomalies_stop_batch_without_advancing_manifest(self):
        self.collect(extra=('--symbols', '2330', '2454'))
        previous = (self.root/'snapshots/retrieval_manifest.json').read_bytes()
        for bad_row in ('1151116,11510,9999,Future,1\n',
                        '1151114,11510,9999,MixedReport,1\n',
                        '1151115,11509,9999,MixedMonth,1\n',
                        '1151115,11511,9999,FuturePeriod,1\n',
                        'not-a-date,11510,9999,Invalid,1\n'):
            with self.subTest(row=bad_row):
                before = set((self.root/'snapshots').glob('retrieval-failure-*.json'))
                with self.assertRaises(ValueError):
                    self.collect((COMPANY, REVENUE + bad_row.encode()), extra=('--symbols', '2330', '2454'))
                reports = set((self.root/'snapshots').glob('retrieval-failure-*.json')) - before
                failure = json.loads(reports.pop().read_text())['failure']
                self.assertEqual(failure['stage'], 'full_file_profile')
                self.assertEqual(failure['error_category'], 'date_contract')
                self.assertEqual(failure['profile']['row_count'], 3)
                self.assertEqual((self.root/'snapshots/retrieval_manifest.json').read_bytes(), previous)

    def test_older_company_report_date_is_distinct_from_retrieval_and_revenue(self):
        manifest = self.collect((COMPANY.replace(b'1151115', b'1151114'), REVENUE))
        profile = manifest['datasets'][0]['profile']
        self.assertEqual(profile['report_dates'], {'2026-11-14': 2})
        self.assertEqual(profile['retrieval_day'], '2026-11-15')
        self.assertEqual(profile['revenue_months'], {})

    def test_missing_fields_and_symbols_have_structured_failure_evidence(self):
        self.collect(extra=('--symbols', '2330', '2454'))
        previous = (self.root/'snapshots/retrieval_manifest.json').read_bytes()
        cases = [(REVENUE.replace('營業收入-當月營收'.encode(), b'unknown'), 'source_schema'),
                 (REVENUE.replace(b'2454', b'9999'), 'source_coverage')]
        for revenue, category in cases:
            with self.subTest(category=category):
                before = set((self.root/'snapshots').glob('retrieval-failure-*.json'))
                with self.assertRaises(ValueError):
                    self.collect((COMPANY, revenue), extra=('--symbols', '2330', '2454'))
                reports = set((self.root/'snapshots').glob('retrieval-failure-*.json')) - before
                failure = json.loads(reports.pop().read_text())['failure']
                self.assertEqual(failure['error_category'], category)
                self.assertEqual(failure['profile']['row_count'], 2)
                if category == 'source_coverage':
                    self.assertEqual(failure['profile']['selection']['missing'], ['TW:2454'])
                self.assertEqual((self.root/'snapshots/retrieval_manifest.json').read_bytes(), previous)

    def test_absent_content_type_is_explicit(self):
        manifest = self.collect(content_type=None)
        self.assertIsNone(manifest['datasets'][0]['content_type'])
        self.assertEqual(manifest['datasets'][0]['content_type_status'], 'missing')

    def test_incomplete_http_body_is_not_a_complete_snapshot(self):
        response = Response(COMPANY, self.sources[0]['resource_url'])
        response.headers['Content-Length'] = str(len(COMPANY) + 20)
        with patch('local.collect_official.build_opener') as build:
            build.return_value.open.side_effect = [response, Response(REVENUE, self.sources[1]["resource_url"])]
            with self.assertRaisesRegex(ValueError, 'length'):
                collect_main(['--registry', str(self.registry), '--output-dir', str(self.root/'snapshots')])
        failure = json.loads(next((self.root/'snapshots').glob('retrieval-failure-*.json')).read_text())['failure']
        self.assertEqual(failure['error_category'], 'response_length')
        self.assertTrue(failure['body_truncated'])
        self.assertIsNone(failure['sha256'])
        self.assertEqual((self.root/'snapshots'/failure['path']).read_bytes(), COMPANY)
