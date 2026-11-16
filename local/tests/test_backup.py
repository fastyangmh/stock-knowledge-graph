import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from local.backup import create, verify, restore
from local.core import ROOT

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source.db'
        self.conn=sqlite3.connect(self.source);self.addCleanup(self.conn.close)
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('CREATE TABLE evidence(value TEXT)');self.conn.execute("INSERT INTO evidence VALUES('first')");self.conn.commit()
    def bundle(self):return create(self.source,self.root/'backups')
    def test_consistent_backup_includes_committed_wal_and_restores(self):
        self.conn.execute("INSERT INTO evidence VALUES('committed-wal')");self.conn.commit()
        bundle=self.bundle();self.assertGreater(verify(bundle)['bytes'],0)
        restored=restore(bundle,self.root/'restored.db')
        with sqlite3.connect(restored) as conn:
            self.assertEqual(conn.execute('SELECT value FROM evidence').fetchall(),[('first',),('committed-wal',)])
    def test_never_overwrites_existing_restore_file(self):
        bundle=self.bundle();target=self.root/'target.db';target.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError,'must not exist'):restore(bundle,target)
        self.assertEqual(target.read_bytes(),b'keep')
    def test_changed_backup_bytes_rejected(self):
        bundle=self.bundle()
        with (bundle/'database.sqlite').open('ab') as out:out.write(b'corruption')
        with self.assertRaisesRegex(ValueError,'checksum'):verify(bundle)
    def test_bad_manifest_rejected(self):
        bundle=self.bundle();(bundle/'manifest.json').write_text('{}')
        with self.assertRaises(ValueError):verify(bundle)
    def test_symlinks_rejected(self):
        link=self.root/'link.db';link.symlink_to(self.source)
        with self.assertRaises(ValueError):create(link,self.root/'backup')
    def test_public_directory_rejected(self):
        with self.assertRaises(ValueError):create(self.source,ROOT/'data')
    def test_missing_source_not_created(self):
        missing=self.root/'missing.db'
        with self.assertRaises(ValueError):create(missing,self.root/'backups')
        self.assertFalse(missing.exists())
    def test_multiple_backups_are_immutable(self):
        first=self.bundle();before=(first/'database.sqlite').read_bytes()
        self.conn.execute("INSERT INTO evidence VALUES('later')");self.conn.commit()
        second=self.bundle();self.assertNotEqual(first,second)
        self.assertEqual((first/'database.sqlite').read_bytes(),before)
    def test_nonsqlite_file_fails_without_success_bundle(self):
        bad=self.root/'bad.db';bad.write_text('not sqlite')
        with self.assertRaises(sqlite3.DatabaseError):create(bad,self.root/'backups')
        self.assertEqual(list((self.root/'backups').iterdir()),[])
    def test_concurrent_target_creation_is_not_overwritten(self):
        bundle=self.bundle();target=self.root/'target.db'
        import os
        original=os.link
        def race(source,destination):
            Path(destination).write_bytes(b'other writer')
            return original(source,destination)
        with patch('local.backup.os.link',side_effect=race),self.assertRaises(FileExistsError):restore(bundle,target)
        self.assertEqual(target.read_bytes(),b'other writer')
