"""Dual-source tests use synthetic lists, never real TW50/ETF data or a network.

Core/SQLite operations are real. CLI dependency injection isolates the new
argument wiring from pre-existing HTTP/model adapters; these are not live tests.
"""
import csv
import hashlib
import importlib.util
import io
import json
import sqlite3
import sys
import tempfile
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

from local.combined_universe import load_combined_universe, TW50, ETF
from local.core import init_db, import_payload
from local.universe import load_universe

ROOT = Path(__file__).resolve().parents[2]
DAY = "2026-11-16"
INDEX_URL = "https://example.org/authorized-index-fixture"
ETF_URL = "https://example.org/authorized-etf-fixture"


def isolated_cli(name, replacements):
    """Load actual CLI source under an alias with only specified IO dependencies mocked."""
    spec = importlib.util.spec_from_file_location("local._test_" + name, ROOT / "local" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, replacements):
        spec.loader.exec_module(module)
    return module


def fake_module(name, **members):
    module = types.ModuleType(name)
    for key, value in members.items():
        setattr(module, key, value)
    return module


class CombinedUniverseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index = self.root / "tw50.csv"
        self.holdings = self.root / "009816.csv"
        # Arbitrary fixture IDs; this is NOT an actual constituent list.
        self.index_rows = [[f"TW:{i:04d}", "2026-01-01", ""] for i in range(1000, 1050)]
        self.etf_rows = [[f"TW:{i:04d}", DAY, ETF_URL] for i in range(1040, 1070)]
        self.write_index()
        self.write_holdings()

    def write_index(self):
        with self.index.open("w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["stock_id", "effective_from", "effective_to"])
            writer.writerows(self.index_rows)

    def write_holdings(self):
        with self.holdings.open("w", encoding="utf-8", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(["stock_id", "snapshot_date", "source_url"])
            writer.writerows(self.etf_rows)

    def load(self):
        return load_combined_universe(self.index, self.holdings, DAY, INDEX_URL)

    def payload(self, selection):
        return {"stocks": [{"stock_id": sid, "ticker": sid.split(":")[1],
                            "market": "TW", "name": "Synthetic " + sid}
                           for sid in sorted(selection.stock_ids)]}

    def database(self):
        conn = sqlite3.connect(self.root / "test.db")
        conn.row_factory = sqlite3.Row
        init_db(conn)
        self.addCleanup(conn.close)
        return conn

    def test_union_counts_not_forced_to_50(self):
        selection = self.load()
        self.assertEqual(selection.metadata()["counts"], {"tw50": 50, "etf_009816": 30, "overlap": 10, "union": 70})
        self.assertEqual(len(selection.stock_ids), 70)

    def test_groups_and_membership_kinds(self):
        selection = self.load()
        self.assertEqual(selection.properties("TW:1000")["universe_group"], "tw50_only")
        self.assertEqual(selection.properties("TW:1040")["universe_group"], "both")
        self.assertEqual(selection.properties("TW:1060")["universe_group"], "etf_009816_only")
        rows = selection.properties("TW:1040")["universe_memberships"]
        self.assertEqual({r["membership_kind"] for r in rows}, {"index_constituent", "etf_holding"})
        self.assertEqual({r["source_url"] for r in rows}, {INDEX_URL, ETF_URL})

    def test_etf_is_only_effective_on_snapshot_date(self):
        row = self.load().properties("TW:1060")["universe_memberships"][0]
        self.assertEqual(row["effective_from"], DAY)
        self.assertEqual(row["effective_to"], DAY)
        with self.assertRaisesRegex(ValueError, "no target-day snapshot"):
            load_combined_universe(self.index, self.holdings, "2026-11-17", INDEX_URL)

    def test_no_backward_fill(self):
        with self.assertRaisesRegex(ValueError, "no target-day snapshot"):
            load_combined_universe(self.index, self.holdings, "2026-11-15", INDEX_URL)

    def test_can_keep_multiple_dated_etf_snapshots(self):
        self.etf_rows += [["TW:1099", "2026-11-15", ETF_URL]]
        self.write_holdings()
        self.assertNotIn("TW:1099", self.load().stock_ids)

    def test_duplicate_same_day_etf_rejected(self):
        self.etf_rows.append(self.etf_rows[0])
        self.write_holdings()
        with self.assertRaisesRegex(ValueError, "duplicate ETF"):
            self.load()

    def test_etf_mixed_sources_rejected(self):
        self.etf_rows[0][2] = "https://example.net/second-source"
        self.write_holdings()
        with self.assertRaisesRegex(ValueError, "one source URL"):
            self.load()

    def test_missing_index_member_rejected(self):
        self.index_rows.pop()
        self.write_index()
        with self.assertRaisesRegex(ValueError, "Expected 50"):
            self.load()

    def test_empty_etf_rejected(self):
        self.etf_rows = []
        self.write_holdings()
        with self.assertRaisesRegex(ValueError, "no target-day snapshot"):
            self.load()

    def test_etf_is_not_required_to_hold_50_stocks(self):
        self.etf_rows = self.etf_rows[:1]
        self.write_holdings()
        self.assertEqual(self.load().metadata()["counts"]["etf_009816"], 1)

    def test_duplicate_index_interval_rejected(self):
        self.index_rows.append(self.index_rows[0])
        self.write_index()
        with self.assertRaisesRegex(ValueError, "overlapping"):
            self.load()

    def test_cash_and_etf_instrument_not_accepted_as_company_ids(self):
        for sid in ("CASH:TWD", "TW:009816", "../private", "TW:abcd"):
            with self.subTest(sid=sid):
                self.etf_rows[0][0] = sid
                self.write_holdings()
                with self.assertRaisesRegex(ValueError, "common-stock"):
                    self.load()

    def test_dates_must_be_valid(self):
        self.etf_rows[0][1] = "2026-02-30"
        self.write_holdings()
        with self.assertRaises(ValueError):
            self.load()

    def test_source_must_not_contain_credentials(self):
        for url in ("", "http://example.com/source", "https://user:secret@example.org/list", "https://a.example/b c"):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    load_combined_universe(self.index, self.holdings, DAY, url)

    def test_input_hashes_recorded(self):
        self.assertEqual(self.load().input_sha256[TW50], hashlib.sha256(self.index.read_bytes()).hexdigest())
        self.assertEqual(self.load().input_sha256[ETF], hashlib.sha256(self.holdings.read_bytes()).hexdigest())

    def test_payload_deduplicates_and_is_not_mutated(self):
        selection = self.load()
        original = self.payload(selection)
        enriched = selection.annotate_payload(original)
        self.assertEqual(len(enriched["stocks"]), 70)
        self.assertNotIn("metadata", original)
        self.assertNotIn("universe_ids", original["stocks"][0])
        self.assertEqual(enriched["metadata"]["research_universe"]["counts"]["union"], 70)

    def test_payload_missing_or_extra_stocks_rejected(self):
        selection = self.load()
        payload = self.payload(selection)
        payload["stocks"].pop()
        with self.assertRaisesRegex(ValueError, "coverage"):
            selection.annotate_payload(payload)
        payload = self.payload(selection)
        payload["stocks"].append(dict(payload["stocks"][0]))
        with self.assertRaisesRegex(ValueError, "coverage"):
            selection.annotate_payload(payload)

    def test_memberships_survive_sqlite_import(self):
        selection = self.load()
        conn = self.database()
        import_payload(conn, selection.annotate_payload(self.payload(selection)))
        import_payload(conn, selection.annotate_payload(self.payload(selection)))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM stocks").fetchone()[0], 70)
        row = conn.execute("SELECT properties_json FROM graph_nodes WHERE node_id='stock:TW:1040'").fetchone()
        props = json.loads(row[0])
        self.assertEqual(props["universe_group"], "both")
        self.assertEqual(props["universe_as_of"], DAY)
        self.assertEqual(len(props["universe_memberships"]), 2)

    def test_export_annotation_requires_complete_existing_nodes(self):
        selection = self.load()
        conn = self.database()
        payload = self.payload(selection)
        payload["stocks"].pop()
        import_payload(conn, payload)
        before = [tuple(r) for r in conn.execute("SELECT node_id,properties_json FROM graph_nodes ORDER BY node_id")]
        with self.assertRaisesRegex(ValueError, "missing from SQLite"):
            selection.annotate_nodes(conn)
        after = [tuple(r) for r in conn.execute("SELECT node_id,properties_json FROM graph_nodes ORDER BY node_id")]
        self.assertEqual(before, after)

    def test_annotation_keeps_source_properties(self):
        selection = self.load()
        conn = self.database()
        payload = self.payload(selection)
        payload["stocks"][0]["attribution"] = "Example source attribution"
        import_payload(conn, payload)
        selection.annotate_nodes(conn)
        props = json.loads(conn.execute("SELECT properties_json FROM graph_nodes WHERE node_id='stock:TW:1000'").fetchone()[0])
        self.assertEqual(props["attribution"], "Example source attribution")
        self.assertEqual(props["universe_group"], "tw50_only")

    def test_legacy_loader_unchanged(self):
        self.assertEqual(len(load_universe(self.index, DAY, expected_count=50)), 50)

    def test_duplicate_csv_headers_rejected(self):
        self.holdings.write_text("stock_id,snapshot_date,source_url,source_url\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "headers"):
            self.load()

    def test_malformed_csv_rows_rejected(self):
        self.holdings.write_text("stock_id,snapshot_date,source_url\nTW:1000," + DAY + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "row length"):
            self.load()

    def test_official_import_passes_union_not_fixed_50(self):
        selection = self.load()
        adapter = Mock(return_value=self.payload(selection))
        writer = Mock()
        cli = isolated_cli("official_import", {
            "local.safety": fake_module("local.safety", private_path=lambda p: p),
            "local.collect_official": fake_module("local.collect_official", atomic_bytes=writer),
            "local.official_adapter": fake_module("local.official_adapter", from_snapshots=adapter),
        })
        with redirect_stdout(io.StringIO()):
            cli.main(["--universe", str(self.index), "--etf-holdings", str(self.holdings),
                      "--universe-source", INDEX_URL, "--as-of", DAY, "--output", str(self.root / "input.json")])
        self.assertEqual(len(adapter.call_args.args[2]), 70)
        output = json.loads(writer.call_args.args[1])
        self.assertEqual(output["metadata"]["research_universe"]["counts"]["overlap"], 10)

    def test_pipeline_all_uses_union_and_real_sqlite(self):
        selection = self.load()
        normalized = self.root / "input.json"
        normalized.write_text(json.dumps(self.payload(selection)), encoding="utf-8")
        compute, exported = Mock(return_value={}), []
        def fake_export(conn, output, *, universe, lifecycle):
            rows = [json.loads(r[0]) for r in conn.execute("SELECT properties_json FROM graph_nodes")]
            exported.append((set(universe), rows))
            return {"stocks": list(universe)}
        cli = isolated_cli("pipeline", {
            "local.similarity": fake_module("local.similarity", compute=compute),
            "local.semantic": fake_module("local.semantic", compute_semantic=compute, DEFAULT_MODEL="fake/test"),
            "local.export_json": fake_module("local.export_json", export=fake_export, validate_graph=Mock()),
        })
        with redirect_stdout(io.StringIO()):
            cli.main(["all", "--input", str(normalized), "--db", str(self.root / "pipeline.db"),
                      "--output", str(self.root / "preview"), "--universe", str(self.index),
                      "--etf-holdings", str(self.holdings), "--universe-source", INDEX_URL, "--as-of", DAY])
        self.assertEqual(len(exported[0][0]), 70)
        self.assertEqual(sum(r["universe_group"] == "both" for r in exported[0][1]), 10)
        self.assertEqual(compute.call_count, 1)

    def test_cli_missing_dual_source_parameters_fails_before_db(self):
        compute = Mock()
        cli = isolated_cli("pipeline", {
            "local.similarity": fake_module("local.similarity", compute=compute),
            "local.semantic": fake_module("local.semantic", compute_semantic=compute, DEFAULT_MODEL="fake/test"),
            "local.export_json": fake_module("local.export_json", export=Mock(), validate_graph=Mock()),
        })
        with patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
            cli.main(["all", "--etf-holdings", str(self.holdings), "--db", str(self.root / "forbidden.db")])
        self.assertFalse((self.root / "forbidden.db").exists())
        compute.assert_not_called()


    def test_after_close_forwards_union_flags_without_publishing(self):
        from datetime import datetime
        normalized = self.root / "input.json"
        normalized.write_text("{}", encoding="utf-8")
        cli = isolated_cli("run_after_close", {
            "local.trading_calendar": fake_module("local.trading_calendar", is_trading_day=lambda *args: True),
        })
        fixed = datetime.fromisoformat(DAY + "T19:00:00+08:00")
        with patch.object(cli, "datetime") as clock, patch.object(cli.subprocess, "run") as run:
            clock.now.return_value = fixed
            with patch("sys.argv", ["after-close", "--calendar", "calendar.csv", "--input", str(normalized),
                 "--universe", str(self.index), "--etf-holdings", str(self.holdings),
                 "--universe-source", INDEX_URL, "--preview-output", str(self.root / "preview")]), redirect_stdout(io.StringIO()):
                cli.main()
        command = run.call_args.args[0]
        self.assertIn("--etf-holdings", command)
        self.assertEqual(command[command.index("--universe-source") + 1], INDEX_URL)
        self.assertEqual(command[command.index("--as-of") + 1], DAY)
        self.assertNotIn("local.publish", command)
        self.assertEqual(run.call_count, 1)

    def test_after_close_still_refuses_publish(self):
        from datetime import datetime
        cli = isolated_cli("run_after_close", {
            "local.trading_calendar": fake_module("local.trading_calendar", is_trading_day=lambda *args: True),
        })
        with patch.object(cli, "datetime") as clock, patch.object(cli.subprocess, "run") as run:
            clock.now.return_value = datetime.fromisoformat(DAY + "T19:00:00+08:00")
            with patch("sys.argv", ["after-close", "--calendar", "calendar.csv", "--input", "unused.json",
                 "--universe", str(self.index), "--etf-holdings", str(self.holdings),
                 "--universe-source", INDEX_URL, "--publish"]), self.assertRaisesRegex(RuntimeError, "not enabled"):
                cli.main()
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
