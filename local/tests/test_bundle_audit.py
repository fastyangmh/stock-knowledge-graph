"""Audit real synthetic SQLite/research bundles, never market downloads."""
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from local.bundle_audit import audit_bundle, catalog, AuditError, main
from local.research_history import canonical
from history_fixtures import make_run


class BundleAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.report=make_run(self.root);self.runs=self.root/'runs';self.name=self.report['run'];self.bundle=self.runs/self.name
    def audit(self,**kw):return audit_bundle(self.runs,self.name,**kw)
    def edit_report(self,mutate):
        path=self.bundle/'report.json';data=json.loads(path.read_text());mutate(data);path.write_bytes(canonical(data))
    def test_complete_bundle_and_latest_anchor(self):
        result,valid=catalog(self.runs)
        self.assertTrue(result['latest_valid']);self.assertEqual(result['counts']['valid'],1)
        self.assertTrue(valid[self.name].anchored)
        self.assertFalse(self.audit().anchored)
        self.assertEqual(valid[self.name].graphs['TW:1000']['research_alerts'],valid[self.name].alerts['stocks']['TW:1000'])
    def test_legacy_bundle_without_configuration_accepted(self):
        self.edit_report(lambda r:r.pop('configuration'))
        self.assertEqual(self.audit().report['engine'],'private-research-1')
    def test_audit_is_read_only(self):
        before={p.relative_to(self.root):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        with patch('sqlite3.connect',side_effect=AssertionError('must not execute database SQL')):self.audit()
        after={p.relative_to(self.root):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_database_tamper(self):
        with (self.bundle/'graph.db').open('ab') as f:f.write(b'bad')
        with self.assertRaisesRegex(AuditError,'database_checksum'):self.audit()
    def test_manifest_tamper(self):
        (self.bundle/'data/manifest.json').write_text('{}')
        with self.assertRaisesRegex(AuditError,'manifest_checksum'):self.audit()
    def test_graph_tamper(self):
        (self.bundle/'data/stocks/1000/graph.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'checksum'):self.audit()
    def test_alert_tamper(self):
        (self.bundle/'alerts.json').write_text('{}')
        with self.assertRaisesRegex(AuditError,'alert_checksum'):self.audit()
    def test_alert_manifest_and_graph_must_match_even_rehashed(self):
        path=self.bundle/'alerts.json';data=json.loads(path.read_text());data['stocks']={};path.write_bytes(canonical(data))
        self.edit_report(lambda r:r['research_alerts'].update(sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        with self.assertRaisesRegex(AuditError,'alert_coverage'):self.audit()
    def test_hash_anchor_mismatch(self):
        with self.assertRaisesRegex(AuditError,'report_pointer'):self.audit(expected_report_sha='f'*64)
    def test_missing_db_is_not_a_complete_run(self):
        (self.bundle/'graph.db').unlink()
        with self.assertRaisesRegex(AuditError,'incomplete'):self.audit()
    def test_report_coverage_conflict(self):
        self.edit_report(lambda r:r['selection'].update(stock_ids=['TW:1000','TW:1001']))
        with self.assertRaisesRegex(AuditError,'coverage'):self.audit()
    def test_future_cutoff(self):
        self.edit_report(lambda r:r.update(known_at='2099-01-01T00:00:00Z'))
        with self.assertRaisesRegex(AuditError,'future'):self.audit()
    def test_wrong_run_and_incomplete_state(self):
        self.edit_report(lambda r:r.update(run='f'*32,status='running'))
        with self.assertRaisesRegex(AuditError,'invalid_bundle_report'):self.audit()
    def test_new_extra_file_is_rejected_not_served(self):
        (self.bundle/'private-token.txt').write_text('TOP SECRET')
        with self.assertRaisesRegex(AuditError,'unexpected'):self.audit()
    def test_symlink_rejected(self):
        (self.bundle/'extra').symlink_to(self.root/'input-1.json')
        with self.assertRaisesRegex(AuditError,'symlink'):self.audit()
    def test_unsafe_run_ids(self):
        for value in ('../private','https://example.org',None,'f'*31,'G'*32):
            with self.subTest(value=value),self.assertRaises(AuditError):audit_bundle(self.runs,value)
    def test_size_budget_before_parse(self):
        with patch('local.bundle_audit.strict_json',side_effect=AssertionError('do not parse')):
            with self.assertRaisesRegex(AuditError,'budget'):self.audit(max_bytes=1)
    def test_corrupt_run_disabled_in_catalog(self):
        make_run(self.root,2);(self.bundle/'graph.db').write_bytes(b'bad')
        summary,valid=catalog(self.runs)
        self.assertEqual(summary['counts']['invalid'],1);self.assertNotIn(self.name,valid)
        self.assertTrue(summary['latest_valid'])
    def test_root_budget_and_total_byte_budget(self):
        make_run(self.root,2)
        with self.assertRaisesRegex(AuditError,'run_budget'):catalog(self.runs,max_runs=1)
        with self.assertRaisesRegex(AuditError,'size_budget'):catalog(self.runs,max_bytes=1)
    def test_stage_residue_reported_never_deleted(self):
        stage=self.runs/'.research-stage-fixture';stage.mkdir();(stage/'scratch').write_text('keep')
        summary,_=catalog(self.runs)
        self.assertEqual(summary['counts']['staging_residues'],1);self.assertTrue((stage/'scratch').exists())
    def test_missing_pointer_is_not_guessed(self):
        (self.runs/'latest.json').unlink();summary,_=catalog(self.runs)
        self.assertIsNone(summary['latest']);self.assertFalse(summary['latest_valid'])
    def test_unknown_root_file_rejected(self):
        (self.runs/'notes').write_text('private')
        with self.assertRaisesRegex(AuditError,'unexpected_research_root'):catalog(self.runs)
    def test_invalid_latest_pointer_not_silently_fallback(self):
        (self.runs/'latest.json').write_text('{"run":"../../private"}')
        with self.assertRaisesRegex(AuditError,'latest_pointer'):catalog(self.runs)
    def test_cli_exit_status(self):
        with redirect_stdout(io.StringIO()) as out:self.assertEqual(main(['--root',str(self.runs)]),0)
        self.assertEqual(json.loads(out.getvalue())['counts']['valid'],1)
        (self.bundle/'graph.db').write_bytes(b'bad')
        with redirect_stdout(io.StringIO()):self.assertEqual(main(['--root',str(self.runs)]),1)
    def test_corrupt_prior_data_stops_next_run(self):
        pointer=(self.runs/'latest.json').read_bytes();(self.bundle/'alerts.json').write_text('{}')
        with self.assertRaisesRegex(AuditError,'alert_checksum'):make_run(self.root,2)
        self.assertEqual((self.runs/'latest.json').read_bytes(),pointer)
    def test_no_alert_bundle_supported(self):
        result=make_run(self.root,2,alerts=False);bundle=audit_bundle(self.runs,result['run'])
        self.assertIsNone(bundle.alerts);self.assertFalse(bundle.summary()['alerts_enabled'])
