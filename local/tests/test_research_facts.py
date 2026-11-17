"""Unpruned facts observed only through research -> audit -> archive."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local.bundle_audit import audit_bundle
from local.research import run
from local.research_history import canonical
from test_research_history import payload, T0, T1, T2, T3


class ResearchFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.input = self.root/'input.json'
        self.runs = self.root/'runs'
        self.data = payload()
        self.input.write_bytes(canonical(self.data))

    def execute(self, *, recorded_at=T1, completed_at=T3, known_at=T1, **options):
        with patch('local.research.utc_now', return_value=completed_at), patch('local.research_history.utc_now', return_value=recorded_at):
            report = run(self.input, ['1000'], history_db=self.root/'ledger.db',
                         output_root=self.runs, known_at=known_at, **options)
        return audit_bundle(self.runs, report['run'])

    def test_all_financial_and_chip_facts_survive_two_display_caps(self):
        metric = self.data['financial_metrics'][0]
        self.data['financial_metrics'] = [{**metric, 'metric': f'metric_{n:03}', 'value': n} for n in range(125)]
        self.data['chip_metrics'] = [{'stock_id': 'TW:1000', 'source_id': 'synthetic',
            'trade_date': '2020-01-02', 'metric': 'synthetic_holdings', 'value': 17,
            'unit': 'shares', 'available_at': T1}]
        self.input.write_bytes(canonical(self.data))
        small = self.execute(max_information_nodes=2)
        large = self.execute(max_information_nodes=100)
        self.assertEqual(small.facts, large.facts)
        self.assertEqual(len(small.facts['facts']), 126)
        self.assertEqual(len(small.graphs['TW:1000']['nodes']), 3)
        self.assertEqual(len(large.graphs['TW:1000']['nodes']), 101)
        self.assertEqual(small.summary()['fact_scope'], 'unpruned_facts')
        fact = next(f for f in small.facts['facts'] if f['kind'] == 'financial_metric')
        self.assertEqual(fact['unit'], 'source_reported')
        self.assertEqual(fact['recorded_at'], T1)
        self.assertEqual(fact['source_available_at'], '2020-01-02T08:00:00+00:00')
        self.assertEqual(small.facts['scope']['market'], {'included': False, 'market': None, 'trade_date': None})

    def test_all_saved_market_history_is_verified_without_inventing_registration(self):
        from local.market_prices import ingest
        from test_market_graph import CSV
        from datetime import date, timedelta
        database, snapshots = self.root/'market.db', self.root/'raw'
        for offset in range(25):
            day = (date(2019, 12, 9) + timedelta(days=offset)).isoformat()
            raw = CSV.replace(b'20200102', day.replace('-', '').encode())
            ingest(raw, 'twse', ['1000'], day, db=database, output=snapshots,
                   observed_at=T1, acquisition='local_file_unverified')
        bundle = self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
        smaller = self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02', max_information_nodes=0)
        self.assertEqual(smaller.facts, bundle.facts)
        self.assertEqual(len(smaller.graphs['TW:1000']['nodes']), 1)
        prices = [f for f in bundle.facts['facts'] if f['kind'] == 'market_price']
        self.assertEqual(len(prices), 25)
        self.assertEqual(sorted(f['trade_date'] for f in prices)[0], '2019-12-09')
        self.assertTrue(all(f['recorded_at'] is None and f['recorded_at_status'] == 'unknown' for f in prices))
        self.assertTrue(all(f['raw_snapshot_verified'] for f in prices))
        self.assertEqual(bundle.facts['scope']['market'], {'included': True, 'market': 'twse', 'trade_date': '2020-01-02'})
        self.assertEqual(sum(n['type'] == 'market_price' for n in bundle.graphs['TW:1000']['nodes']), 1)
        old_raw = snapshots/prices[0]['source_id']/(prices[0]['raw_sha256']+'.csv')
        old_raw.write_bytes(b'tampered')
        pointer = (self.runs/'latest.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
        self.assertEqual((self.runs/'latest.json').read_bytes(), pointer)

    def test_rehashed_unknown_schema_is_rejected_instead_of_display_fallback(self):
        bundle = self.execute()
        path = self.runs/bundle.report['run']/'research-facts.json'
        facts = json.loads(path.read_text())
        facts['schema_version'] = 'research-facts-999'
        self.rewrite_facts(bundle, facts)
        with self.assertRaisesRegex(ValueError, 'facts_schema'):
            audit_bundle(self.runs, bundle.report['run'])

    def rewrite_facts(self, bundle, facts):
        import hashlib
        directory = self.runs/bundle.report['run']
        body = canonical(facts)
        (directory/'research-facts.json').write_bytes(body)
        report = copy.deepcopy(bundle.report)
        report['research_facts'].update(sha256=hashlib.sha256(body).hexdigest(), size_bytes=len(body))
        (directory/'report.json').write_bytes(canonical(report))

    def test_rehashed_facts_reject_future_foreign_stock_and_invalid_provenance(self):
        bundle = self.execute()
        changes = [
            ('stock_id', 'TW:9999'), ('available_at', '2099-01-01T00:00:00Z'),
            ('observed_at', '2099-01-01T00:00:00Z'), ('recorded_at', None),
            ('source_available_at', '2099-01-01T00:00:00Z'),
            ('input_snapshot_sha256', 'f'*64), ('source_id', 'unresolved'),
            ('value', True), ('period_end', '2099-01-01'), ('id', 'forged'),
        ]
        for field, value in changes:
            with self.subTest(field=field):
                facts = copy.deepcopy(bundle.facts)
                facts['facts'][0][field] = value
                self.rewrite_facts(bundle, facts)
                with self.assertRaises(ValueError):
                    audit_bundle(self.runs, bundle.report['run'])

    def test_fact_entry_limit_fails_whole_run_and_preserves_old_pointer(self):
        first = self.execute()
        pointer = (self.runs/'latest.json').read_bytes()
        with patch('local.research_facts.MAX_FACTS', 0):
            with self.assertRaisesRegex(ValueError, 'facts_entry_budget'):
                self.execute()
        self.assertEqual((self.runs/'latest.json').read_bytes(), pointer)
        self.assertEqual(len(list(self.runs.glob('*/report.json'))), 1)
        self.assertEqual(audit_bundle(self.runs, first.report['run']).facts, first.facts)

    def test_rehashed_index_and_fact_coverage_are_required(self):
        bundle = self.execute()
        for change in ('count', 'size_bytes'):
            report = copy.deepcopy(bundle.report)
            report['research_facts'][change] += 1
            (self.runs/bundle.report['run']/'report.json').write_bytes(canonical(report))
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'facts_'):
                audit_bundle(self.runs, bundle.report['run'])

    def test_preview_budget_counts_served_graphs_not_private_facts(self):
        from local.research_archive import archive_snapshot
        self.data['metadata']['private_evidence_note'] = 'x' * (1024*1024)
        self.input.write_bytes(canonical(self.data))
        bundle = self.execute()
        files, _ = archive_snapshot(self.runs)
        served_budget = sum(len(body) for body, mime in files.values()) + 1024
        self.assertLess(served_budget, 1024*1024)
        served, bundles = archive_snapshot(self.runs, max_preview_bytes=served_budget)
        self.assertIn(bundle.report['run'], bundles)
        self.assertFalse(any('research-facts.json' in path for path in served))

    def test_legacy_bundle_remains_readable_and_cannot_claim_unpruned_facts(self):
        bundle = self.execute()
        directory = self.runs/bundle.report['run']
        report = copy.deepcopy(bundle.report)
        report.pop('research_facts')
        (directory/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'unlisted_facts'):
            audit_bundle(self.runs, bundle.report['run'])
        (directory/'research-facts.json').unlink()
        legacy = audit_bundle(self.runs, bundle.report['run'])
        self.assertIsNone(legacy.facts)
        self.assertEqual(legacy.summary()['fact_scope'], 'display_graph_only')

    def test_new_contract_missing_hash_missing_file_and_symlink_fail_closed(self):
        bundle = self.execute()
        directory = self.runs/bundle.report['run']
        path = directory/'research-facts.json'
        original = path.read_bytes()
        path.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'facts_checksum'):
            audit_bundle(self.runs, bundle.report['run'])
        path.unlink()
        with self.assertRaisesRegex(ValueError, 'facts_checksum'):
            audit_bundle(self.runs, bundle.report['run'])
        target = self.root/'facts.json'
        target.write_bytes(original)
        path.symlink_to(target)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            audit_bundle(self.runs, bundle.report['run'])
        path.unlink()
        path.write_bytes(original)
        report = copy.deepcopy(bundle.report)
        report['research_facts'].pop('sha256')
        (directory/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'facts_checksum'):
            audit_bundle(self.runs, bundle.report['run'])

    def test_fact_json_and_whole_bundle_have_independent_size_limits(self):
        bundle = self.execute()
        path = self.runs/bundle.report['run']/'research-facts.json'
        with path.open('wb') as stream:
            stream.truncate(32*1024*1024+1)
        with self.assertRaisesRegex(ValueError, 'json_size_budget'):
            audit_bundle(self.runs, bundle.report['run'])
        path.write_bytes(canonical(bundle.facts))
        with self.assertRaisesRegex(ValueError, 'bundle_size_budget'):
            audit_bundle(self.runs, bundle.report['run'], max_bytes=1024)

    def test_zero_numeric_facts_have_explicit_coverage_without_fabrication(self):
        self.data['financial_metrics'] = []
        self.input.write_bytes(canonical(self.data))
        bundle = self.execute()
        self.assertEqual(bundle.facts['facts'], [])
        self.assertEqual(bundle.facts['coverage'], {'TW:1000': {'financial_metric': 0, 'chip_metric': 0, 'market_price': 0}})

    def test_history_work_limits_stop_without_partial_facts_or_new_pointer(self):
        from local.market_prices import ingest
        from test_market_graph import CSV
        database, snapshots = self.root/'market.db', self.root/'raw'
        ingest(CSV, 'twse', ['1000'], '2020-01-02', db=database, output=snapshots,
               observed_at=T1, acquisition='local_file_unverified')
        self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
        pointer = (self.runs/'latest.json').read_bytes()
        for policy in ('MAX_HISTORY_ROWS', 'MAX_HISTORY_RAW_BYTES', 'MAX_HISTORY_RECORD_BYTES'):
            with self.subTest(policy=policy), patch('local.market_graph.'+policy, 0):
                with self.assertRaisesRegex(ValueError, 'work budget'):
                    self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
                self.assertEqual((self.runs/'latest.json').read_bytes(), pointer)
        self.assertEqual(len(list(self.runs.glob('*/report.json'))), 1)

    def test_cutoff_and_late_registration_do_not_backfill_earlier_bundle(self):
        first = self.execute()
        original = (self.runs/first.report['run']/'research-facts.json').read_bytes()
        self.data['metadata']['observed_at'] = T2
        self.data['financial_metrics'][0].update(value=1500, available_at=T2)
        self.input.write_bytes(canonical(self.data))
        late = self.execute(recorded_at=T2, known_at=T2)
        earlier = self.execute(recorded_at=T3, known_at=T1)
        self.assertEqual(late.facts['facts'][0]['value'], 1500)
        self.assertEqual(earlier.facts['facts'][0]['value'], 1000)
        self.assertEqual((self.runs/first.report['run']/'research-facts.json').read_bytes(), original)
        self.assertEqual(earlier.facts, first.facts)

    def test_future_availability_excluded_and_raw_normalization_provenance_retained(self):
        metric = self.data['financial_metrics'][0]
        metric.update(normalization_version='synthetic-v1', raw_value='1000',
                      raw_unit='source_reported', currency='TWD', consolidation='consolidated', value_basis='monthly')
        self.data['financial_metrics'].append({**metric, 'metric': 'future_metric', 'available_at': T2})
        self.data['metadata']['source_snapshots'] = [{'dataset_id': 'synthetic', 'sha256': 'a'*64, 'path': 'synthetic.csv'}]
        self.input.write_bytes(canonical(self.data))
        bundle = self.execute()
        self.assertEqual(len(bundle.facts['facts']), 1)
        fact = bundle.facts['facts'][0]
        self.assertEqual(fact['normalization_version'], 'synthetic-v1')
        self.assertEqual((fact['raw_value'], fact['raw_unit'], fact['currency'], fact['consolidation'], fact['value_basis']),
                         ('1000', 'source_reported', 'TWD', 'consolidated', 'monthly'))
        self.assertEqual(bundle.facts['normalized_snapshots'][0]['metadata']['source_snapshots'], self.data['metadata']['source_snapshots'])

    def test_sql_scan_budget_is_enforced_for_saved_history(self):
        from local.market_prices import ingest
        from test_market_graph import CSV
        from datetime import date, timedelta
        database, snapshots = self.root/'market.db', self.root/'raw'
        for offset in range(160):
            day = (date(2019, 7, 27)+timedelta(days=offset)).isoformat()
            ingest(CSV.replace(b'20200102', day.replace('-', '').encode()), 'twse', ['1000'], day,
                   db=database, output=snapshots, observed_at=T1, acquisition='local_file_unverified')
        with patch('local.market_graph.MAX_HISTORY_SQL_STEPS', 0):
            with self.assertRaisesRegex(ValueError, 'SQL work budget'):
                self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
        self.assertFalse((self.runs/'latest.json').exists())

    def test_audit_checks_entry_limit_and_report_replay_coverage(self):
        bundle = self.execute()
        with patch('local.research_facts.MAX_FACTS', 0):
            with self.assertRaisesRegex(ValueError, 'facts_entry_budget'):
                audit_bundle(self.runs, bundle.report['run'])
        facts = copy.deepcopy(bundle.facts)
        facts['facts'] = []
        facts['coverage']['TW:1000']['financial_metric'] = 0
        self.rewrite_facts(bundle, facts)
        directory = self.runs/bundle.report['run']
        report = json.loads((directory/'report.json').read_text())
        report['research_facts']['count'] = 0
        (directory/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'replay_count'):
            audit_bundle(self.runs, bundle.report['run'])

    def test_malformed_facts_are_disabled_in_catalog_without_crashing_other_runs(self):
        from local.bundle_audit import catalog
        bundle = self.execute()
        (self.runs/'latest.json').unlink()
        for field, value in (('scope', []), ('scope', {'stock_ids': ['TW:1000'], 'known_at': bundle.report['known_at'], 'market': []})):
            facts = copy.deepcopy(bundle.facts)
            facts[field] = value
            self.rewrite_facts(bundle, facts)
            with self.subTest(value=value):
                summary, valid = catalog(self.runs)
                self.assertEqual(summary['counts']['invalid'], 1)
                self.assertEqual(valid, {})

    def test_financial_source_provenance_resolves_to_its_normalized_snapshot(self):
        bundle = self.execute()
        facts = copy.deepcopy(bundle.facts)
        facts['facts'][0]['source']['provider'] = 'different source owner'
        self.rewrite_facts(bundle, facts)
        with self.assertRaisesRegex(ValueError, 'source_provenance'):
            audit_bundle(self.runs, bundle.report['run'])

    def test_market_history_respects_cutoff_target_and_unknown_registration(self):
        from local.market_prices import ingest
        from test_market_graph import CSV
        database, snapshots = self.root/'market.db', self.root/'raw'
        for raw, day, observed in ((CSV, '2020-01-02', T1),
                (CSV.replace(b'11.00', b'12.00'), '2020-01-02', T2),
                (CSV.replace(b'20200102', b'20200103'), '2020-01-03', T2)):
            ingest(raw, 'twse', ['1000'], day, db=database, output=snapshots,
                   observed_at=observed, acquisition='local_file_unverified')
        bundle = self.execute(prices_db=database, price_snapshots=snapshots, trade_date='2020-01-02')
        prices = [fact for fact in bundle.facts['facts'] if fact['kind'] == 'market_price']
        self.assertEqual([(fact['trade_date'], fact['close']) for fact in prices], [('2020-01-02', '11.00')])
        facts = copy.deepcopy(bundle.facts)
        fact = next(f for f in facts['facts'] if f['kind'] == 'market_price')
        fact.update(recorded_at=fact['observed_at'], recorded_at_status='known')
        self.rewrite_facts(bundle, facts)
        with self.assertRaisesRegex(ValueError, 'invented_market_time'):
            audit_bundle(self.runs, bundle.report['run'])
