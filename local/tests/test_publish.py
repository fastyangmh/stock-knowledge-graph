"""Publication tests use temporary local bare remotes, never GitHub."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from local.publish import publish, git

class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'work';self.root.mkdir()
        self.remote=Path(self.tmp.name)/'remote.git'
        subprocess.run(['git','init','--bare','--initial-branch=main',str(self.remote)],check=True,capture_output=True)
        for args in [('init','--initial-branch=main'),('config','user.name','Test'),('config','user.email','test@example.invalid'),('remote','add','origin',str(self.remote))]:git(*args,root=self.root)
        path=self.root/'data/stocks/2330/graph.json';path.parent.mkdir(parents=True)
        graph={'stock_id':'TW:2330','nodes':[{'id':'stock:TW:2330','type':'stock','label':'Synthetic'}],'edges':[]}
        path.write_text(json.dumps(graph))
        self.manifest=self.root/'data/manifest.json'
        self.manifest.write_text(json.dumps({'stocks':[{'label':'Synthetic','path':'data/stocks/2330/graph.json'}]}))
        git('add','.',root=self.root);git('commit','-m','test base',root=self.root);git('push','-u','origin','main',root=self.root)
        self.head=git('rev-parse','HEAD',root=self.root)
        obj=json.loads(self.manifest.read_text());obj['version']='test-2';self.manifest.write_text(json.dumps(obj))
    def tearDown(self):self.tmp.cleanup()
    def test_dry_run_keeps_index_and_commit_unchanged(self):
        self.assertIn('manifest.json',publish(True,root=self.root))
        self.assertEqual(git('diff','--cached','--name-only',root=self.root),'')
        self.assertEqual(git('rev-parse','HEAD',root=self.root),self.head)
    def test_pre_staged_changes_preserved(self):
        git('add','data/manifest.json',root=self.root)
        before=git('diff','--cached',root=self.root)
        with self.assertRaises(RuntimeError):publish(True,root=self.root)
        self.assertEqual(git('diff','--cached',root=self.root),before)
    def test_unrelated_work_not_committed(self):
        (self.root/'notes.txt').write_text('private')
        with self.assertRaises(RuntimeError):publish(True,root=self.root)
        self.assertEqual(git('rev-parse','HEAD',root=self.root),self.head)
    def test_commit_to_local_test_remote_only(self):
        self.assertIn('Published',publish(root=self.root))
        self.assertNotEqual(git('rev-parse','HEAD',root=self.root),self.head)
        self.assertEqual(git('show','--format=','--name-only','HEAD',root=self.root).strip(),'data/manifest.json')
