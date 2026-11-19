"""Exercise the portable archive through its operator CLI and restored readers."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

from history_fixtures import make_run
from local.bundle_audit import catalog
from local.event_study import build
from local.research_history import canonical


class PortableBackupTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.run = make_run(self.root)
        self.ledger = self.root / 'history-1.db'
        self.runs = self.root / 'runs'
        self.bundle = self.root / 'archive'
        self.destination = self.root / 'restored'
        self.input = self.root / 'input-1.json'
        self.raw = self.root / 'original.csv'
        self.raw.write_bytes(b'fixture,1\r\n')
        self.event = self.root / 'events.json'
        self.event.write_bytes(canonical(build(self.runs, self.run['completed_at'])))

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, '-m', 'local.portable_backup', *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def create(self, *, ok=True):
        return self.cli('create', '--ledger', self.ledger, '--runs', self.runs, '--input', self.input,
                        '--raw', self.raw, '--event', self.event, '--output', self.bundle, ok=ok)

    def test_archive_and_restore_committed_wal_raw_and_auditable_history(self):
        db = sqlite3.connect(self.ledger)
        self.addCleanup(db.close)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE marker(message)')
        db.execute("INSERT INTO marker VALUES ('committed in WAL')")
        db.commit()
        self.create()
        self.cli('verify', '--bundle', self.bundle)
        self.cli('restore', '--bundle', self.bundle, '--destination', self.destination)
        with sqlite3.connect(self.destination / 'ledger.db') as restored:
            self.assertEqual(restored.execute('SELECT message FROM marker').fetchone(), ('committed in WAL',))
        self.assertEqual((self.destination / 'raw/original.csv').read_bytes(), self.raw.read_bytes())
        summary, _ = catalog(self.destination / 'runs')
        self.assertEqual(summary['latest'], self.run['run'])
        self.assertEqual(build(self.destination / 'runs', self.run['completed_at']), json.loads(self.event.read_bytes()))

    def test_explicit_catalog_budget_survives_verify_and_restore(self):
        from local.research import run
        from local.event_study import analyze
        old = analyze(catalog(self.runs)[1].values(), self.run['completed_at'], cohort_version=None)
        self.event.write_bytes(canonical(old))
        for _ in range(50):
            run(self.input, ['1000'], history_db=self.ledger, output_root=self.runs)
        self.create(ok=False)
        args = ['create', '--ledger', self.ledger, '--runs', self.runs, '--input', self.input,
                '--event', self.event, '--output', self.bundle]
        self.cli(*args, '--max-runs', 501, ok=False)
        self.cli(*args, '--max-mib', 4097, ok=False)
        self.cli(*args, '--max-runs', 51, '--max-mib', 32)
        self.cli('verify', '--bundle', self.bundle)
        self.cli('restore', '--bundle', self.bundle, '--destination', self.destination)
        self.assertEqual(catalog(self.destination/'runs', max_runs=51)[0]['counts']['valid'], 51)

    def test_missing_original_input_and_wrong_event_reference_fail_without_publishing(self):
        original_pointer = (self.runs / 'latest.json').read_bytes()
        original_input = self.input.read_bytes()
        self.input.write_bytes(original_input + b'\n')
        self.create(ok=False)
        self.assertFalse(self.bundle.exists())
        self.input.write_bytes(original_input)
        event = json.loads(self.event.read_bytes())
        event['inputs'][0]['report_sha256'] = 'f' * 64
        self.event.write_bytes(canonical(event))
        self.create(ok=False)
        self.assertFalse(self.bundle.exists())
        self.assertEqual((self.runs / 'latest.json').read_bytes(), original_pointer)

    def test_commit_to_wal_during_copy_rejects_archive_and_preserves_pointer(self):
        from local.portable_backup import main
        from unittest.mock import patch
        import shutil
        db = sqlite3.connect(self.ledger)
        self.addCleanup(db.close)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE marker(value)")
        db.commit()
        pointer = (self.runs / 'latest.json').read_bytes()
        copy = shutil.copyfileobj

        def write_concurrently(source, destination, **kw):
            if Path(destination.name).name == self.raw.name:
                db.execute('INSERT INTO marker VALUES (1)')
                db.commit()
            return copy(source, destination, **kw)

        with patch('shutil.copyfileobj', side_effect=write_concurrently), self.assertRaises(SystemExit):
            main(['create', '--ledger', str(self.ledger), '--runs', str(self.runs), '--input', str(self.input),
                  '--raw', str(self.raw), '--output', str(self.bundle)])
        self.assertFalse(self.bundle.exists())
        self.assertEqual((self.runs / 'latest.json').read_bytes(), pointer)

    def test_preserves_documents_named_by_financial_unit_evidence(self):
        from hashlib import sha256
        from local.research_history import record_snapshot
        statement = self.root / 'statement.html'
        statement.write_bytes(b'original unit heading')
        receipt = self.root / 'unit-evidence.json'
        receipt.write_bytes(canonical({'schema_version': 'financial-unit-evidence-1.0', 'decisions': [
            {'raw_snapshot_sha256': sha256(self.raw.read_bytes()).hexdigest(), 'references': [
                {'path': statement.name, 'sha256': sha256(statement.read_bytes()).hexdigest()}]}]}))
        payload = json.loads(self.input.read_bytes())
        payload['metadata']['unit_evidence_sha256'] = sha256(receipt.read_bytes()).hexdigest()
        with sqlite3.connect(self.ledger) as db:
            record_snapshot(db, payload)
        args = ['create', '--ledger', self.ledger, '--runs', self.runs, '--input', self.input,
                '--raw', self.raw, '--raw', receipt, '--output', self.bundle]
        self.cli(*args, ok=False)
        self.cli(*args, '--raw', statement)

    def test_restore_preserves_failed_truncated_capture_without_claiming_full_hash(self):
        from local.collect_official import save_failure
        from local.http_evidence import ResponseBytes
        capture = self.root/'attempt'
        save_failure(capture, {'dataset_id': 'fixture', 'resource_url': 'https://example.org'},
                     [], 'fetch', ValueError('incomplete'), ResponseBytes(b'ab', {'body_truncated': True}))
        args = ['create', '--ledger', self.ledger, '--runs', self.runs, '--input', self.input,
                '--raw', capture, '--output', self.bundle]
        self.cli(*args)
        self.cli('restore', '--bundle', self.bundle, '--destination', self.destination)
        [receipt] = (self.destination/'raw/attempt').glob('retrieval-*.json')
        failure = json.loads(receipt.read_bytes())['failure']
        self.assertIsNone(failure['sha256'])
        self.assertEqual((receipt.parent/failure['path']).read_bytes(), b'ab')
        (capture/failure['path']).unlink()
        self.cli(*args[:-1], self.root/'incomplete', ok=False)

    def test_dangling_retrieval_receipt_and_unsafe_recorded_path_fail(self):
        from hashlib import sha256
        evidence = self.root / 'official'
        evidence.mkdir()
        receipt = evidence / 'retrieval_manifest.json'
        args = ['create', '--ledger', self.ledger, '--runs', self.runs, '--input', self.input,
                '--raw', evidence, '--output', self.bundle]
        entry = {'path': 'company/data.csv', 'sha256': sha256(b'raw').hexdigest(), 'bytes': 3}
        receipt.write_bytes(canonical({'datasets': [entry]}))
        self.cli(*args, ok=False)
        (evidence / 'company').mkdir()
        (evidence / entry['path']).write_bytes(b'raw')
        receipt.write_bytes(canonical({'datasets': [{**entry, 'path': 'company/../company/data.csv'}]}))
        self.cli(*args, ok=False)
        receipt.write_bytes(canonical({'datasets': [entry]}))
        self.cli(*args)

    def test_manifest_path_class_and_extra_entry_cannot_redirect_restore(self):
        self.create()
        manifest = self.bundle / 'manifest.json'
        original = manifest.read_bytes()
        for field, value in [('path', '../outside'), ('class', 'raw'), ('sha256', '0' * 64)]:
            index = json.loads(original)
            entry = next(e for e in index['files'] if e['path'] == 'ledger.db')
            entry[field] = value
            manifest.write_bytes(canonical(index))
            with self.subTest(field=field):
                self.cli('restore', '--bundle', self.bundle, '--destination', self.destination, ok=False)
                self.assertFalse(self.destination.exists())
        manifest.write_bytes(original)
        (self.bundle / 'payload/empty-undeclared').mkdir()
        self.cli('verify', '--bundle', self.bundle, ok=False)

    def test_missing_or_linked_evidence_and_existing_destination_are_rejected(self):
        import os
        self.create()
        self.destination.mkdir()
        self.cli('restore', '--bundle', self.bundle, '--destination', self.destination, ok=False)
        self.assertEqual(list(self.destination.iterdir()), [])
        member = self.bundle / 'payload/raw' / self.raw.name
        member.unlink()
        self.cli('verify', '--bundle', self.bundle, ok=False)
        member.symlink_to(self.raw)
        self.cli('verify', '--bundle', self.bundle, ok=False)
        member.unlink()
        os.link(self.raw, member)
        self.cli('verify', '--bundle', self.bundle, ok=False)
        self.assertEqual(self.raw.read_bytes(), b'fixture,1\r\n')

    def test_new_writer_and_partial_copy_do_not_replace_existing_research(self):
        import shutil
        from unittest.mock import patch
        from local.portable_backup import main
        self.create()
        pointer = (self.runs / 'latest.json').read_bytes()
        copy = shutil.copyfileobj
        args = ['restore', '--bundle', str(self.bundle), '--destination', str(self.destination)]

        def interrupted(source, target, **kw):
            target.write(b'partial')
            raise OSError('interrupted copy')

        with patch('shutil.copyfileobj', side_effect=interrupted), self.assertRaises(SystemExit):
            main(args)
        self.assertFalse(self.destination.exists())

        def racer(source, target, **kw):
            self.destination.mkdir(exist_ok=True)
            return copy(source, target, **kw)

        with patch('shutil.copyfileobj', side_effect=racer), self.assertRaises(SystemExit):
            main(args)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual((self.runs / 'latest.json').read_bytes(), pointer)

    def test_pointer_change_during_create_rejects_candidate(self):
        import shutil
        from unittest.mock import patch
        from local.portable_backup import main
        pointer = self.runs / 'latest.json'
        copy = shutil.copyfileobj

        def update(source, target, **kw):
            if Path(target.name).name == self.raw.name:
                pointer.write_bytes(pointer.read_bytes() + b'\n')
            return copy(source, target, **kw)

        args = ['create', '--ledger', str(self.ledger), '--runs', str(self.runs), '--input', str(self.input),
                '--raw', str(self.raw), '--output', str(self.bundle)]
        with patch('shutil.copyfileobj', side_effect=update), self.assertRaises(SystemExit):
            main(args)
        self.assertFalse(self.bundle.exists())
        self.assertTrue(catalog(self.runs)[0]['latest_valid'])

    def test_archive_root_and_index_are_private(self):
        import stat
        self.create()
        self.assertEqual(stat.S_IMODE(self.bundle.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.bundle / 'manifest.json').stat().st_mode), 0o600)
