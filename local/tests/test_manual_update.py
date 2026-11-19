"""Manual operations exercised through the CLI using private files and SQLite."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


def save(path, document):
    path.write_text(json.dumps(document), encoding='utf-8')


class ManualUpdateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base/'work'
        self.market = self.root/'twse'
        raw = self.base/'calendar.txt'
        raw.write_bytes(b'synthetic calendar')
        self.calendar = self.base/'calendar.json'
        save(self.calendar, {'schema_version': 'market-calendar-1', 'entries': [{
            'id': 'calendar-test', 'market': 'twse', 'start': '2019-12-31', 'end': '2020-01-03',
            'source_url': 'https://example.org/calendar', 'date_semantics': 'fixture',
            'retrieved_at': '2019-12-20T08:00:00Z', 'saved_at': '2019-12-20T09:00:00Z',
            'path': raw.name, 'sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
            'days': {'2020-01-01': 'closed', '2020-01-02': 'open', '2020-01-03': 'open'}}]})
        self.plan = {'market': 'twse', 'symbols': ['1000'], 'trade_date': '2020-01-02',
                     'as_of': '2020-01-02', 'calendar': str(self.calendar)}

    def invoke(self, job='daily', through='audit'):
        from local.manual_update import main
        plan_path = self.base/'plan.json'
        save(plan_path, self.plan)
        code = main(['--root', str(self.root), '--plan', str(plan_path),
                     '--job', job, '--through', through])
        report = json.loads((self.market/'jobs'/job/'report.json').read_bytes())
        return code, report

    def test_calendar_holiday_skips_sources_and_preserves_latest(self):
        self.plan['trade_date'] = '2020-01-01'
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report['calendar']['market_status'], 'closed')
        self.assertGreater(report['disk']['free'], 0)
        self.assertEqual(report['stages']['prices']['status'], 'skipped')
        self.assertFalse((self.market/'runs/latest.json').exists())

    def replay_sources(self):
        from local.core import ROOT
        from local.tests.test_market_prices import fixture
        sources = [s for s in json.loads((ROOT/'local/official_datasets.json').read_bytes())
                   if s['enabled']]
        snapshots = self.base/'snapshots'
        snapshots.mkdir()
        datasets = []
        for source, csv in zip(sources, [
            '出表日期,公司代號,公司名稱\n1090102,1000,測試\n',
            '出表日期,資料年月,公司代號,公司名稱,營業收入-當月營收\n1090102,10812,1000,測試,100\n']):
            path = snapshots/(source['dataset_id']+'.csv')
            body = csv.encode()
            path.write_bytes(body)
            datasets.append({'dataset_id': source['dataset_id'], 'path': path.name,
                             'retrieved_at': '2020-01-02T09:00:00Z', 'bytes': len(body),
                             'resource_url': source['resource_url'],
                             'sha256': hashlib.sha256(body).hexdigest()})
        manifest = snapshots/'retrieval_manifest.json'
        save(manifest, {'schema_version': '1.0', 'datasets': datasets})
        prices = self.base/'prices.csv'
        prices.write_bytes(fixture())
        self.plan.update(financial_dir=str(snapshots),
                         financial_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),
                         price_file=str(prices), price_sha256=hashlib.sha256(prices.read_bytes()).hexdigest(),
                         expected_revenue_month='2019-12')

    def test_full_replay_promotes_audited_research_and_separate_reminders(self):
        from local.bundle_audit import audit_bundle
        self.replay_sources()
        code, report = self.invoke()
        self.assertEqual(code, 0)
        pointer = json.loads((self.market/'runs/latest.json').read_bytes())
        bundle = audit_bundle(self.market/'runs', pointer['run'], expected_report_sha=pointer['report_sha256'])
        self.assertEqual(set(bundle.alerts['stocks']['TW:1000']['categories']), {'monthly_revenue', 'price_volume'})
        self.assertEqual(report['stages']['normalize']['revenue_months'], ['2019-12'])
        self.assertEqual(report['stages']['prices']['trade_date'], '2020-01-02')
        self.assertEqual(report['last_success'], pointer['run'])

    def test_monthly_archive_requires_replayable_receipt_and_registry(self):
        from local.portable_backup import main
        from local.core import ROOT
        from local.research import run
        self.replay_sources()
        code, _ = self.invoke(through='normalize')
        self.assertEqual(code, 0)
        normalized = self.market/'jobs/daily/input.json'
        runs = self.base/'runs'
        ledger = self.base/'ledger.db'
        run(normalized, ['1000'], output_root=runs, history_db=ledger)
        snapshots = Path(self.plan['financial_dir'])
        archive = self.base/'archive'
        args = ['create', '--input', str(normalized), '--ledger', str(ledger), '--runs', str(runs),
                '--output', str(archive)]
        with self.assertRaises(SystemExit):
            main(args + [v for p in snapshots.glob('*.csv') for v in ('--raw', str(p))])
        with self.assertRaises(SystemExit):
            main(args + ['--raw', str(snapshots)])
        registry = self.base/'registry.json'
        registry.write_bytes((ROOT/'local/official_datasets.json').read_bytes())
        main(args + ['--raw', str(snapshots), '--config', str(registry)])
        main(['restore', '--bundle', str(archive), '--destination', str(self.base/'restored')])
        manifest = archive/'manifest.json'
        legacy = json.loads(manifest.read_bytes())
        legacy['schema_version'] = 'private-research-backup-1'
        del legacy['catalog_limits']
        legacy['audit']['references'] = [row for row in legacy['audit']['references']
                                         if row['field'] not in ('acquisition_receipt_sha256', 'source_registry_sha256')]
        save(manifest, legacy)
        main(['verify', '--bundle', str(archive)])

    def test_same_job_retry_and_candidate_audit_failure_keep_prior_success(self):
        self.replay_sources()
        self.assertEqual(self.invoke()[0], 0)
        pointer = self.market/'runs/latest.json'
        old = pointer.read_bytes()
        code, retry = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(pointer.read_bytes(), old)
        self.assertEqual(retry['stages']['prices']['inserted'], 0)
        code, partial = self.invoke('next', through='research')
        self.assertEqual(code, 0)
        self.assertEqual(pointer.read_bytes(), old)
        candidate = self.market/'jobs/next/candidate'/partial['stages']['research']['run']
        (candidate/'alerts.json').write_bytes(b'{}')
        code, failed = self.invoke('next')
        self.assertEqual(code, 2)
        self.assertEqual(failed['stages']['research']['status'], 'failed')
        self.assertEqual(failed['last_success'], json.loads(old)['run'])
        self.assertEqual(pointer.read_bytes(), old)
        code, repaired = self.invoke('next', through='research')
        self.assertEqual(code, 0, repaired)
        self.assertNotEqual(repaired['stages']['research']['run'], partial['stages']['research']['run'])
        self.assertEqual(pointer.read_bytes(), old)
        self.assertEqual(self.invoke('next')[0], 0)

    def test_partial_download_retries_only_missing_source_and_records_attempts(self):
        from unittest.mock import patch
        from local.tests.test_official_collection import Response
        self.replay_sources()
        self.assertEqual(self.invoke('prior')[0], 0)
        old = (self.market/'runs/latest.json').read_bytes()
        snapshots = Path(self.plan.pop('financial_dir'))
        self.plan.pop('financial_manifest_sha256')
        price = Path(self.plan.pop('price_file')).read_bytes()
        self.plan.pop('price_sha256')
        self.plan.update(download_financial=True, download_prices=True)
        collected = json.loads((snapshots/'retrieval_manifest.json').read_bytes())['datasets']
        company, revenue = [Response((snapshots/s['path']).read_bytes(), s['resource_url']) for s in collected]
        with patch('local.collect_official.build_opener') as client, \
             patch('local.collect_official.now', return_value='2020-01-02T09:03:00Z'):
            client.return_value.open.side_effect = [company, OSError('feed unavailable')]
            code, failed = self.invoke('online')
            self.assertEqual(code, 2)
            self.assertEqual(failed['stages']['acquire']['failed_source'], 'twse_monthly_revenue')
            self.assertEqual((self.market/'runs/latest.json').read_bytes(), old)
            client.return_value.open.side_effect = [revenue]
            with patch('local.market_prices.build_opener') as prices:
                prices.return_value.open.return_value = Response(price, 'https://www.twse.com.tw/')
                code, result = self.invoke('online')
                self.assertEqual(code, 0, result)
        self.assertEqual(result['stages']['prices']['acquisition'], 'https_download')
        self.assertEqual(len(list((self.market/'jobs/online/attempts').glob('*.json'))), 2)

    def test_freshness_calendar_and_disk_failure_never_replace_last_success(self):
        self.replay_sources()
        self.assertEqual(self.invoke('prior')[0], 0)
        pointer = self.market/'runs/latest.json'
        old = pointer.read_bytes()
        base = self.plan.copy()
        cases = [('month', {'expected_revenue_month': '2020-01'}, 'acquire', 'stale'),
                 ('oldquote', {'trade_date': '2020-01-03'}, 'prices', 'stale'),
                 ('unknown', {'trade_date': '2020-01-04'}, 'calendar', 'unknown'),
                 ('disk', {'min_free_bytes': 10**18}, 'preflight', 'low_disk'),
                 ('missing', {'price_file': str(self.base/'missing.csv')}, 'prices', 'missing')]
        for job, changes, stage, kind in cases:
            with self.subTest(job=job):
                self.plan = {**base, **changes}
                code, report = self.invoke(job)
                self.assertEqual(code, 2)
                self.assertEqual(report['stages'][stage]['kind'], kind)
                self.assertEqual(report['last_success'], json.loads(old)['run'])
                self.assertEqual(pointer.read_bytes(), old)

    def test_inability_to_save_update_report_keeps_last_success(self):
        from local.manual_update import main
        self.replay_sources()
        self.assertEqual(self.invoke('prior')[0], 0)
        old = (self.market/'runs/latest.json').read_bytes()
        self.assertEqual(self.invoke('next', through='research')[0], 0)
        report_path = self.market/'jobs/next/report.json'
        report_path.unlink()
        report_path.mkdir()
        code = main(['--root', str(self.root), '--plan', str(self.base/'plan.json'),
                     '--job', 'next'])
        self.assertNotEqual(code, 0)
        self.assertEqual((self.market/'runs/latest.json').read_bytes(), old)
        from local.bundle_audit import catalog
        from local.event_study import build
        from local.research_history import utc_now
        self.assertEqual(set(catalog(self.market/'runs')[1]), {json.loads(old)['run']})
        events = build(self.market/'runs', utc_now())
        self.assertEqual([row['run'] for row in events['inputs']], [json.loads(old)['run']])
        report_path.rmdir()
        self.assertEqual(self.invoke('next')[0], 0)
        self.assertEqual(catalog(self.market/'runs')[0]['counts']['valid'], 2)

    def test_newer_price_observation_cannot_silently_replace_job_input(self):
        self.replay_sources()
        self.assertEqual(self.invoke('first', 'prices')[0], 0)
        original = self.plan.copy()
        new_price = self.base/'different.csv'
        new_price.write_bytes(Path(original['price_file']).read_bytes().replace(b'11.50', b'11.60'))
        self.plan.update(price_file=str(new_price), price_sha256=hashlib.sha256(new_price.read_bytes()).hexdigest())
        self.assertEqual(self.invoke('second')[0], 0)
        old = (self.market/'runs/latest.json').read_bytes()
        self.plan = original
        code, report = self.invoke('first')
        self.assertEqual(code, 2)
        self.assertIn('price', report['stages']['audit']['reason'])
        self.assertEqual((self.market/'runs/latest.json').read_bytes(), old)

    def test_on_confirmed_closure_verified_same_day_quote_is_a_conflict(self):
        self.replay_sources()
        price = Path(self.plan['price_file'])
        price.write_bytes(price.read_bytes().replace(b'1090102', b'1090101'))
        self.plan.update(trade_date='2020-01-01', price_sha256=hashlib.sha256(price.read_bytes()).hexdigest())
        code, report = self.invoke()
        self.assertEqual(code, 2)
        self.assertEqual(report['calendar']['market_status'], 'conflict')
        self.assertFalse((self.market/'runs/latest.json').exists())

    def test_online_retry_can_replace_stale_monthly_receipt_without_refetching_company(self):
        from unittest.mock import patch
        from local.tests.test_official_collection import Response
        self.replay_sources()
        snapshots = Path(self.plan.pop('financial_dir'))
        self.plan.pop('financial_manifest_sha256')
        self.plan['download_financial'] = True
        rows = json.loads((snapshots/'retrieval_manifest.json').read_bytes())['datasets']
        def response(row, stale=False):
            body = (snapshots/row['path']).read_bytes()
            return Response(body.replace(b'10812', b'10811') if stale else body, row['resource_url'])
        with patch('local.collect_official.build_opener') as client, \
             patch('local.collect_official.now', return_value='2020-01-02T09:03:00Z'):
            client.return_value.open.side_effect = [response(rows[0]), response(rows[1], stale=True)]
            code, failed = self.invoke()
            self.assertEqual(code, 2)
            client.return_value.open.side_effect = [response(rows[1])]
            code, success = self.invoke()
            self.assertEqual(code, 0, success)
            self.assertEqual(success['stages']['normalize']['revenue_months'], ['2019-12'])

    def test_retry_reuses_company_after_invalid_selected_revenue(self):
        from unittest.mock import patch
        from local.tests.test_official_collection import Response
        self.replay_sources()
        snapshots = Path(self.plan.pop('financial_dir'))
        self.plan.pop('financial_manifest_sha256')
        self.plan['download_financial'] = True
        company, revenue = json.loads((snapshots/'retrieval_manifest.json').read_bytes())['datasets']
        def response(row, invalid=False):
            body = (snapshots/row['path']).read_bytes()
            return Response(body.replace(b',100\n', b',ERR\n') if invalid else body, row['resource_url'])
        with patch('local.collect_official.build_opener') as client, \
             patch('local.collect_official.now', return_value='2020-01-02T09:03:00Z'):
            client.return_value.open.side_effect = [response(company), response(revenue, True)]
            self.assertEqual(self.invoke()[0], 2)
            client.return_value.open.side_effect = [response(revenue)]
            code, result = self.invoke()
            self.assertEqual(code, 0, result)

    def test_replay_revalidates_pins_and_cannot_promote_over_another_job(self):
        self.replay_sources()
        code, _ = self.invoke('staged', 'research')
        self.assertEqual(code, 0)
        self.assertEqual(self.invoke('winner')[0], 0)
        old = (self.market/'runs/latest.json').read_bytes()
        code, rejected = self.invoke('staged')
        self.assertEqual(code, 2)
        self.assertIn('advanced', rejected['stages']['audit']['reason'])
        raw = Path(self.plan['financial_dir'])/'twse_companies.csv'
        raw.write_bytes(raw.read_bytes() + b' ')
        code, altered = self.invoke('winner')
        self.assertEqual(code, 2)
        self.assertEqual(altered['stages']['acquire']['failed_source'], 'twse_companies')
        self.assertEqual((self.market/'runs/latest.json').read_bytes(), old)
