"""Synthetic source-issued notices through research and its saved bundle auditor."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from local.bundle_audit import audit_bundle
from local.research import run
from local.tests.test_research_history import T0, T1, T2, payload


class SourceRevisionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name).resolve()
        self.runs = self.root / 'runs'
        self.base = payload()
        self.original = self.submit(self.base)

    def submit(self, data, **options):
        path = self.root / 'input.json'
        path.write_text(json.dumps(data))
        return run(path, ['1000'], history_db=self.root / 'history.db', output_root=self.runs, **options)

    def notice(self, target, action='withdraw', *, observed=T1, value=2000, group='financial_metrics'):
        data = payload(observed, value)
        record = data[group][0]
        key = {field: record[field] for field in
               ('document_id', 'stock_id', 'metric', 'period_type', 'period_end', 'trade_date')
               if field in record and (group != 'documents' or field == 'document_id')}
        for name in ('documents', 'financial_metrics', 'chip_metrics'):
            data[name] = [record] if name == group and action != 'withdraw' else []
        data['stocks'] = data['stocks'][:1]
        data['source_revision'] = {
            'schema_version': 'source-revision-1', 'action': action, 'group': group, 'key': key,
            'source_id': 'synthetic', 'target_snapshot_sha256': target['registered_snapshot']['sha256'],
            'effective_at': observed, 'published_at': observed,
            'source_reference': 'fixture:notice/01', 'evidence': 'Synthetic notice with an explicit target and action.',
        }
        return data

    def values(self, report):
        bundle = audit_bundle(self.runs, report['run'])
        return [fact['value'] for fact in bundle.facts['facts']]

    def test_withdrawal_replays_at_local_cutoff_and_old_bundle_remains_intact(self):
        old_report = self.runs / self.original['run'] / 'report.json'
        old_hash = hashlib.sha256(old_report.read_bytes()).hexdigest()
        data = self.notice(self.original)
        new = self.submit(data, enable_source_revisions=True)
        self.assertEqual(self.values(new), [])
        self.assertEqual(self.values(self.submit(data, known_at=self.original['known_at'])), [1000])
        self.assertEqual(self.values(self.original), [1000])
        self.assertEqual(hashlib.sha256(old_report.read_bytes()).hexdigest(), old_hash)
        entry, = new['quality']['source_revisions']
        self.assertEqual(entry['notice'], data['source_revision'])
        self.assertEqual(entry['recorded_at'], new['registered_snapshot']['recorded_at'])

    def test_correction_omission_late_input_withdrawal_and_republication(self):
        corrected = self.submit(self.notice(self.original, 'correct'), enable_source_revisions=True)
        self.assertEqual(self.values(corrected), [2000])
        omitted = payload(T2)
        omitted['financial_metrics'] = []
        self.assertEqual(self.values(self.submit(omitted)), [2000])
        withdraw = self.notice(corrected, observed=T2)
        gone = self.submit(withdraw)
        self.assertEqual(self.values(gone), [])
        repeated = self.submit(withdraw)
        self.assertFalse(repeated['registered_snapshot']['inserted'])
        self.assertEqual(repeated['registered_snapshot']['recorded_at'], gone['registered_snapshot']['recorded_at'])
        late = payload(T0)
        late['metadata']['note'] = 'late older copy'
        self.assertEqual(self.values(self.submit(late)), [])
        self.assertEqual(self.values(self.submit(payload('2020-01-10T00:00:00Z'))), [])
        restored = self.submit(self.notice(gone, 'republish', observed='2020-01-11T00:00:00Z', value=3500))
        self.assertEqual(self.values(restored), [3500])
        self.assertEqual(len(restored['quality']['source_revisions']), 3)

    def test_unresolved_targets_conflicts_and_unsupported_source_do_not_poison_retry(self):
        pointer = self.runs / 'latest.json'
        before = pointer.read_bytes()
        valid = self.notice(self.original)
        invalid = copy.deepcopy(valid)
        invalid['source_revision']['target_snapshot_sha256'] = '1' * 64
        with self.assertRaisesRegex(ValueError, 'target'):
            self.submit(invalid, enable_source_revisions=True)
        self.assertEqual(pointer.read_bytes(), before)
        wrong_source = copy.deepcopy(valid)
        wrong_source['source_revision']['source_id'] = wrong_source['sources'][0]['source_id'] = 'another'
        with self.assertRaisesRegex(ValueError, 'source|target'):
            self.submit(wrong_source, enable_source_revisions=True)
        bad_group = copy.deepcopy(valid)
        bad_group['source_revision']['group'] = 'market_price'
        with self.assertRaisesRegex(ValueError, 'unsupported'):
            self.submit(bad_group, enable_source_revisions=True)
        self.assertEqual(pointer.read_bytes(), before)
        first = self.submit(valid, enable_source_revisions=True)
        before = pointer.read_bytes()
        with self.assertRaisesRegex(ValueError, 'conflict|target'):
            self.submit(self.notice(self.original, 'correct'))
        self.assertEqual(pointer.read_bytes(), before)
        self.assertEqual(self.values(self.submit(valid)), [])
        self.assertEqual(self.values(first), [])

    def test_audit_rejects_falsified_notice_even_for_historical_unpinned_run(self):
        new = self.submit(self.notice(self.original), enable_source_revisions=True)
        path = self.runs / new['run'] / 'report.json'
        new = json.loads(path.read_bytes())
        new['quality']['source_revisions'][0]['notice']['evidence'] = 'unrelated text'
        path.write_text(json.dumps(new))
        with self.assertRaisesRegex(ValueError, 'revision'):
            audit_bundle(self.runs, new['run'])

    def test_document_and_chip_notices_keep_selection_and_original_evidence(self):
        base = payload(T1)
        base['chip_metrics'] = [{'stock_id': 'TW:1000', 'source_id': 'synthetic', 'metric': 'net_flow',
                                 'trade_date': '2020-01-02', 'value': 12, 'available_at': T1}]
        prior = self.submit(base)
        doc_notice = self.notice(prior, observed=T2, group='documents')
        gone = self.submit(doc_notice, enable_source_revisions=True)
        graph = audit_bundle(self.runs, gone['run']).graphs['TW:1000']
        self.assertFalse(any(node['type'] == 'financial' for node in graph['nodes']))
        chip_notice = copy.deepcopy(doc_notice)
        chip_notice['source_revision'].update(group='chip_metrics', key={
            'stock_id': 'TW:1000', 'metric': 'net_flow', 'trade_date': '2020-01-02'})
        removed = self.submit(chip_notice)
        self.assertEqual(self.values(removed), [1000])
        self.assertEqual(len(audit_bundle(self.runs, prior['run']).facts['facts']), 2)

    def test_migration_checks_legacy_bytes_and_does_not_rewrite_old_rows(self):
        import sqlite3
        with sqlite3.connect(self.root / 'history.db') as db:
            original_rows = list(db.execute('SELECT * FROM research_snapshots'))
        with self.assertRaisesRegex(ValueError, 'enable-source-revisions'):
            self.submit(self.notice(self.original))
        with sqlite3.connect(self.root / 'history.db') as db:
            db.execute("UPDATE research_snapshots SET payload_json=replace(payload_json, 'Synthetic A', 'Synthetic X')")
        with self.assertRaisesRegex(ValueError, 'legacy|prior snapshot'):
            self.submit(self.base, enable_source_revisions=True)
        with sqlite3.connect(self.root / 'history.db') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 0)
            db.execute("UPDATE research_snapshots SET payload_json=?", (original_rows[0][3],))
        self.submit(self.base, enable_source_revisions=True)
        with sqlite3.connect(self.root / 'history.db') as db:
            self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0], 1)
            self.assertEqual(list(db.execute('SELECT * FROM research_snapshots')), original_rows)

    def test_future_effective_withdrawal_keeps_current_value(self):
        data = self.notice(self.original)
        data['source_revision']['effective_at'] = '2099-01-02T00:00:00Z'
        new = self.submit(data, enable_source_revisions=True)
        self.assertEqual(self.values(new), [1000])
        self.assertEqual(new['quality']['source_revisions'], [])

    def test_restatement_cannot_change_source_provider_using_a_known_id(self):
        data = self.notice(self.original)
        data['sources'][0]['provider'] = 'Unrelated company'
        with self.assertRaisesRegex(ValueError, 'source'):
            self.submit(data, enable_source_revisions=True)

    def test_saved_event_keeps_its_first_baseline_after_source_withdrawal(self):
        from local.event_study import build
        from local.research_history import utc_now
        data = payload(T1)
        metric = dict(data['financial_metrics'][0], metric='monthly_revenue_yoy_pct', value=42, unit='percent')
        data['financial_metrics'].append(metric)
        trigger = self.submit(data, alerts=True)
        before = build(self.runs, utc_now())['categories']['monthly_revenue']['events']
        self.assertEqual(len(before), 1)
        withdrawal = self.notice(trigger, observed=T2)
        withdrawal['source_revision']['key']['metric'] = 'monthly_revenue_yoy_pct'
        self.submit(withdrawal, enable_source_revisions=True, alerts=True)
        after = build(self.runs, utc_now())['categories']['monthly_revenue']['events']
        self.assertEqual(after, before)

    def test_same_observation_and_registration_use_explicit_version_order(self):
        from unittest.mock import patch
        from local.research_history import canonical, utc_now
        clock = utc_now()
        with patch('local.research_history.utc_now', return_value=clock), patch('local.research.utc_now', return_value=clock):
            change = self.notice(self.original, 'correct', observed=T2)
            change['source_revision']['published_at'] = T1
            prior = self.submit(change, enable_source_revisions=True)
            withdrawal = self.notice(prior, observed=T2)
            # The child's content hash sorts before its causal parent.
            for n in range(1000):
                withdrawal['metadata']['fixture'] = n
                if hashlib.sha256(canonical(withdrawal)).hexdigest() < prior['registered_snapshot']['sha256']:
                    break
            self.assertEqual(self.values(self.submit(withdrawal)), [])
