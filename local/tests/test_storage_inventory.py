"""Private storage operator CLI acceptance, using real files and links."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


class StorageInventoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "source"
        self.root.mkdir()
        self.output = self.base / "inventory.json"

    def cli(self, *options, expected=0, output=None):
        result = subprocess.run(
            [sys.executable, "-m", "local.storage_inventory", "--root", str(self.root),
             "--output", str(output or self.output), *map(str, options)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stderr)

    def test_totals_are_reproducible_from_files_and_aliases(self):
        with sqlite3.connect(self.root / "history.db") as connection:
            connection.execute("CREATE TABLE observed (id INTEGER)")
        db_bytes = (self.root / "history.db").stat().st_size
        for name, size in {"history.db-wal": 5, "evidence/a.csv": 12, "runs/id/result": 1,
                           "backups/one/bad": 2, "models/weights": 3, "invalid": 7}.items():
            path = self.root / name
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(bytes(size))
        os.link(self.root / "invalid", self.root / "invalid-copy")
        (self.root / "link").symlink_to(self.base, target_is_directory=True)
        self.cli("--class", "raw=evidence", "--budget", "raw=10")
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report["bytes_by_category"], {
            "database": db_bytes + 5, "raw": 12, "bundle": 1, "backup": 2,
            "model": 3, "unknown": 7})
        self.assertEqual(report["total_bytes"], db_bytes + 30)
        self.assertEqual(report["total_bytes"], sum(e["counted_bytes"] for e in report["files"]))
        entries = {e["path"]: e for e in report["files"]}
        self.assertEqual(entries["link"]["type"], "symlink")
        self.assertEqual(entries["invalid-copy"]["same_file_as"], "invalid")
        self.assertEqual(report["budget_exceeded"], [
            {"category": "raw", "limit_bytes": 10, "observed_bytes": 12,
             "excess_bytes": 2, "paths": ["evidence/a.csv"]}])

    def test_growth_rejects_unrelated_baselines_and_never_overwrites(self):
        (self.root / "grow").write_bytes(b"12")
        (self.root / "gone").write_bytes(b"123")
        self.cli()
        before = self.output.read_bytes()
        (self.root / "grow").write_bytes(b"123456")
        (self.root / "gone").unlink()
        (self.root / "new").write_bytes(b"12")
        next_report = self.base / "second.json"
        self.cli("--previous", self.output, output=next_report)
        growth = json.loads(next_report.read_bytes())["growth"]
        self.assertEqual(growth["total_delta_bytes"], 3)
        self.assertEqual([(e["path"], e["change"], e["size_delta_bytes"]) for e in growth["files"]],
                         [("gone", "removed", -3), ("grow", "changed", 4), ("new", "added", 2)])
        self.cli(expected=2)
        self.assertEqual(self.output.read_bytes(), before)
        self.cli(output=self.root / "report.json", expected=2)
        self.assertFalse((self.root / "report.json").exists())
        self.root = self.base / "unrelated"
        self.root.mkdir()
        self.cli("--previous", self.output, output=self.base / "wrong.json", expected=2)
        self.assertFalse((self.base / "wrong.json").exists())

    def test_archive_plan_links_pointer_event_bundle_and_evidence_and_retains_unknown(self):
        from hashlib import sha256
        run = "a" * 32
        bundle = self.root / "runs" / run
        bundle.mkdir(parents=True)
        raw = self.root / "raw.csv"
        raw.write_bytes(b"test bytes")
        fixture = {"run": run, "engine": "private-research-1", "status": "complete",
                   "market_observations": [{"raw_sha256": sha256(raw.read_bytes()).hexdigest()}],
                   "input_sha256": "1" * 64}
        bundle_report = bundle / "report.json"
        bundle_report.write_text(json.dumps(fixture))
        pointer = {"run": run, "report_sha256": sha256(bundle_report.read_bytes()).hexdigest()}
        (bundle.parent / "latest.json").write_text(json.dumps(pointer))
        (self.root / "event-one.json").write_text(json.dumps({"inputs": [pointer]}))
        (self.root / "broken.json").write_text("{")
        self.cli()
        plan = json.loads(self.output.read_bytes())["archive_plan"]
        self.assertEqual(plan["originals"], "retain_all")
        target = str(bundle_report.relative_to(self.root))
        self.assertEqual(plan["bundle_copies"], [{"directory": f"runs/{run}", "report": target,
            "referenced_by": ["event-one.json", "runs/latest.json"]}])
        refs = plan["references"][target]
        self.assertEqual({r["field"]: r["status"] for r in refs},
                         {"input_sha256": "unresolved", "raw_sha256": "matched_bytes"})
        self.assertEqual(plan["content_paths"][fixture["market_observations"][0]["raw_sha256"]], ["raw.csv"])
        self.assertIn({"path": "broken.json", "reason": "invalid_json"}, plan["uninspected"])

    def test_growth_distinguishes_an_unreadable_directory_from_a_removal(self):
        if os.geteuid() == 0:
            self.skipTest("root can read mode-000 directories")
        locked = self.root / "restricted"
        locked.mkdir()
        (locked / "original").write_bytes(b"data")
        self.cli()
        locked.chmod(0)
        try:
            output = self.base / "partial.json"
            self.cli("--previous", self.output, output=output, expected=2)
            report = json.loads(output.read_bytes())
        finally:
            locked.chmod(0o700)
        self.assertFalse(report["size_complete"])
        self.assertEqual(report["scan_errors"][0]["path"], "restricted")
        self.assertEqual(report["growth"]["files"][0]["change"], "unobserved")
        self.assertIsNone(report["growth"]["total_delta_bytes"])

    def test_unknown_path_and_uninspected_content_are_retained(self):
        (self.root / "orphan.json").write_text('{"path":"../external.csv"}')
        (self.root / "weights.bin").write_bytes(bytes(200))
        (self.root / "bad.json").symlink_to(self.base / "missing")
        self.cli("--content-budget", 64)
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report["total_bytes"], 226)
        plan = report["archive_plan"]
        self.assertEqual(plan["references"]["orphan.json"],
                         [{"field": "path", "declared_path": "../external.csv",
                           "sha256": None, "status": "unresolved"}])
        self.assertEqual(plan["uninspected"], [{"path": "bad.json", "reason": "symlink"},
                                               {"path": "weights.bin", "reason": "content_budget"}])

    def test_research_runs_root_is_recognized_without_a_wrapper(self):
        self.root = self.root / "research-runs"
        self.root.mkdir()
        (self.root / "latest.json").write_bytes(b"bad")
        self.cli()
        report = json.loads(self.output.read_bytes())
        self.assertEqual(report["bytes_by_category"]["bundle"], 3)

    def test_external_evidence_locator_can_match_bytes_in_another_directory(self):
        from hashlib import sha256
        (self.root / "registry").mkdir()
        (self.root / "registry" / "source.pdf").write_bytes(b"source")
        digest = sha256(b"source").hexdigest()
        (self.root / "research-facts.json").write_text(json.dumps({
            "evidence": {"path": "source.pdf", "sha256": digest}}))
        self.cli()
        plan = json.loads(self.output.read_bytes())["archive_plan"]
        self.assertEqual(plan["references"]["research-facts.json"], [
            {"field": "sha256", "sha256": digest, "declared_path": "source.pdf", "status": "matched_bytes"}])

    def test_bundle_directory_as_root_preserves_dependencies(self):
        run = 'a' * 32
        self.root = self.root/'runs'/run
        self.root.mkdir(parents=True)
        (self.root/'report.json').write_text(json.dumps({
            'engine': 'private-research-1', 'run': run, 'status': 'complete',
            'source_id': 'fixture', 'input_sha256': '1'*64}))
        self.cli()
        report = json.loads(self.output.read_bytes())
        plan = report['archive_plan']
        self.assertEqual(plan['bundle_copies'][0]['report'], 'report.json')
        self.assertEqual(plan['bundle_requirements']['report.json']['source_ids'], ['fixture'])
        self.assertEqual(plan['references']['report.json'][0]['status'], 'unresolved')
        self.assertEqual(report['bytes_by_category']['bundle'], report['total_bytes'])

    def test_copy_plan_preserves_declared_model_revision_and_source_identifiers(self):
        run = "b" * 32
        bundle = self.root / run
        bundle.mkdir()
        report = {"engine": "private-research-1", "run": run, "status": "complete",
                  "configuration": {"analysis": {"mode": "semantic", "model": "fixture", "revision": "rev"}},
                  "quality": {"snapshots": [{"sources": [{"source_id": "filing"}],
                            "metadata": {"source_snapshots": [{"dataset_id": "raw-filing"}]}}]},
                  "market_observations": [{"source_id": "market"}]}
        (bundle / "report.json").write_text(json.dumps(report))
        self.cli()
        plan = json.loads(self.output.read_bytes())["archive_plan"]
        self.assertEqual(plan["bundle_requirements"][f"{run}/report.json"],
                         {"source_ids": ["filing", "market"], "dataset_ids": ["raw-filing"],
                          "model": {"id": "fixture", "revision": "rev"}})
