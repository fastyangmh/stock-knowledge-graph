"""Read archived synthetic research results through the private quality CLI."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from history_fixtures import make_run


class QualityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def report(self, *options, filename="quality.json", cutoff="2021-01-01T00:00:00Z"):
        from local.alert_quality import main
        destination = self.root / filename
        with contextlib.redirect_stdout(io.StringIO()):
            main(["--root", str(self.root / "runs"), "--as-of", cutoff,
                  "--output", str(destination), *options])
        return json.loads(destination.read_bytes())

    def test_first_saved_denominator_shows_all_six_rules_and_excluded_runs(self):
        first = make_run(self.root, 1, value=10)
        disabled = make_run(self.root, 2, alerts=False)
        future = make_run(self.root, 3)
        result = self.report(cutoff=disabled["completed_at"])
        self.assertEqual(result["inputs"][future["run"]]["status"], "after_analysis_cutoff")
        self.assertEqual(result["inputs"][disabled["run"]]["status"], "alerts_not_computed")
        self.assertEqual(result["inputs"][first["run"]]["status"], "included")
        groups = result["rules"]
        self.assertEqual(len(groups), 6)
        self.assertEqual(groups["revenue_yoy"]["first_saved"]["not_triggered"], 1)
        self.assertEqual(groups["price_change"]["first_saved"]["insufficient_data"], 1)
        self.assertEqual(groups["price_change"]["first_saved"]["evaluable"], 0)
        self.assertEqual(groups["revenue_mom"]["first_saved"]["triggered"], 1)
        self.assertEqual(sum(r["saved"]["total"] for r in groups.values()), 6)

    def test_equivalent_decimal_thresholds_repeat_in_quality_and_event_reports(self):
        from local.event_study import build
        make_run(self.root, 1, config={"revenue_yoy_pct": 30})
        make_run(self.root, 2, config={"revenue_yoy_pct": 30.0})
        report = self.report()
        totals = report["rules"]["revenue_yoy"]
        self.assertEqual((totals["first_saved"]["total"], totals["saved"]["total"]), (1, 2))
        study = build(self.root / "runs", report["as_of"])
        events = [e for e in study["categories"]["monthly_revenue"]["events"] if e["rule_id"] == "revenue_yoy"]
        self.assertEqual([e["repeated_captures"] for e in events], [1])

    def test_repeated_evidence_and_revised_values_have_one_first_saved_case(self):
        first = make_run(self.root, 1, value=10)
        repeated = make_run(self.root, 1, value=10)
        refreshed = make_run(self.root, 2, value=10)
        revised = make_run(self.root, 3, value=42)
        make_run(self.root, 4, value=42, config={"revenue_yoy_pct": 50})
        make_run(self.root, 5, value=42, source="different")
        result = self.report()
        rule = result["rules"]["revenue_yoy"]
        self.assertEqual((rule["saved"]["total"], rule["first_saved"]["total"]), (6, 3))
        self.assertEqual(rule["first_saved"]["triggered"], 1)
        cases = [c for c in result["cases"] if c["rule_id"] == "revenue_yoy"]
        case, = [c for c in cases if len(c["captures"]) == 4]
        self.assertEqual(case["stock_id"], "TW:1000")
        self.assertEqual(case["target_period"], "2020-07-31")
        captures = case["captures"]
        self.assertEqual({r["run"] for r in captures[:2]}, {first["run"], repeated["run"]})
        self.assertEqual([r["change"] for r in captures],
                         ["first_saved", "repeat", "provenance_changed", "value_revised"])
        self.assertEqual(captures[2]["run"], refreshed["run"])
        self.assertEqual(captures[3]["run"], revised["run"])
        self.assertEqual(captures[3]["check"]["value"], "42.000000")
        self.assertEqual(captures[0]["check"]["status"], "not_triggered")
        self.assertEqual(case["definition"]["settings"]["revenue_yoy_pct"], 30)
        self.assertEqual(case["definition"]["sources"][0]["source_id"], "fixture")

    def test_full_window_gap_and_action_evidence_retain_original_rule_denominators(self):
        import csv
        from datetime import date, timedelta
        from hashlib import sha256
        from unittest.mock import patch
        from local.market_prices import FEEDS, ingest
        from local.research import run
        from local.research_history import canonical
        from local.tpex_action_evidence import CATALOG, COLUMNS, RESOURCE
        from test_alerts import payload

        start = date(2020, 8, 1)
        days = [start + timedelta(days=i) for i in range(21)] + [date(2020, 9, 1)]
        db, raw = self.root / "prices.db", self.root / "raw"
        path = self.root / "input.json"
        path.write_bytes(canonical(payload()))
        for i, day in enumerate(days):
            trade_date = day.isoformat()
            known = trade_date + "T13:00:00Z"
            body = io.StringIO(newline="")
            writer = csv.writer(body)
            writer.writerow(FEEDS["tpex"]["columns"])
            close = 110 if i == 20 else 100
            writer.writerow([day.strftime("%Y%m%d"), "1000", "Synthetic", close, close, close, close,
                             2000 if i == 20 else 1000, 200000, 10])
            ingest(body.getvalue().encode(), "tpex", ["1000"], trade_date, db=db, output=raw,
                   observed_at=known, acquisition="local_file_unverified")
            if i >= 20:
                with patch("local.research.utc_now", return_value=known), patch("local.research_history.utc_now", return_value=known):
                    run(path, ["1000"], history_db=self.root / "history.db", output_root=self.root / "runs",
                        alerts=True, known_at=known, prices_db=db, price_snapshots=raw,
                        price_market="tpex", trade_date=trade_date)

        body = io.StringIO(newline="")
        writer = csv.DictWriter(body, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerow({"除權息日期": "20200821", "代號": "1000", "權或息": "息"})
        raw_bytes = body.getvalue().encode()
        (self.root / "11633.response").write_bytes(raw_bytes)
        manifest = self.root / "receipt.json"
        observed = "2020-08-21T12:00:00Z"
        manifest.write_bytes(canonical([dict(id=11633, catalog=CATALOG, url=RESOURCE, status="200",
            exit=0, bytes=len(raw_bytes), sha256=sha256(raw_bytes).hexdigest(), started_at=observed, received_at=observed)]))
        calendar = self.root / "calendar.json"
        (self.root / "calendar.txt").write_bytes(b"synthetic")
        calendar.write_bytes(canonical({"schema_version": "market-calendar-1", "entries": [
            dict(id="sessions", market="tpex", start="2020-08-01", end="2020-09-01", path="calendar.txt",
                 sha256=sha256(b"synthetic").hexdigest(), date_semantics="exchange sessions",
                 retrieved_at=observed, saved_at=observed, source_url="https://example.org/calendar",
                 days={"2020-08-21":"open", "2020-08-25":"open", "2020-09-01":"open"})]}))
        report = self.report("--action-manifest", str(manifest), "--calendar", str(calendar))
        group = report["rules"]["volume_ratio"]["first_saved"]
        self.assertEqual((group["triggered"], group["not_comparable"]), (1, 1))
        cases = [case for case in report["cases"] if case["rule_id"] == "volume_ratio"]
        first, second = [case["captures"][0] for case in cases]
        self.assertEqual(first["check"]["value"], "2.000000")
        self.assertEqual(first["check"]["baseline"]["available_observations"], 20)
        self.assertEqual(first["price_context"]["actions"][0]["row_number"], 2)
        self.assertIn("price_definition_unknown", first["price_context"]["warnings"])
        self.assertEqual(second["check"]["reason"], "observation_gap_exceeds_policy")
        self.assertIn("2020-08-25", second["price_context"]["open_without_window_observation"])
        self.assertIn("capital_reduction", first["price_context"]["unknown_interval_coverage"])

    def test_monthly_raw_receipt_and_explicit_withdrawal_remain_traceable(self):
        from hashlib import sha256
        from unittest.mock import patch
        from local.research import run
        from local.research_history import canonical
        from test_alerts import payload

        data = payload()
        origin = sha256(b"Synthetic monthly CSV").hexdigest()
        data["metadata"]["source_snapshots"] = [{"dataset_id": "fixture", "sha256": origin}]
        path = self.root / "input.json"
        def save(data, known, **kwargs):
            path.write_bytes(canonical(data))
            with patch("local.research.utc_now", return_value=known), patch("local.research_history.utc_now", return_value=known):
                return run(path, ["1000"], history_db=self.root / "ledger.db", output_root=self.root / "runs",
                           known_at=known, alerts=True, **kwargs)
        first = save(data, "2020-08-20T00:00:00Z")
        later = "2020-08-21T00:00:00Z"
        target = first["registered_snapshot"]["sha256"]
        key = dict(stock_id="TW:1000", metric="monthly_revenue_yoy_pct", period_type="month", period_end="2020-07-31")
        data["financial_metrics"] = []
        data["metadata"] = {"observed_at": later}
        data["source_revision"] = dict(schema_version="source-revision-1", action="withdraw",
            group="financial_metrics", key=key, source_id="fixture", target_snapshot_sha256=target,
            effective_at=later, published_at=later, source_reference="fixture:notice/01", evidence="Synthetic note")
        last = save(data, later, enable_source_revisions=True)
        result = self.report()
        self.assertEqual(result["inputs"][first["run"]]["raw_sources"][target][0]["sha256"], origin)
        entry, = result["inputs"][last["run"]]["revision_notices"]
        self.assertEqual((entry["action"], entry["key"], entry["target_snapshot_sha256"]), ("withdraw", key, target))
        totals = result["rules"]["revenue_yoy"]["saved"]
        self.assertEqual(totals["triggered"], 1)
        self.assertEqual(totals["insufficient_data"], 1)
        self.assertEqual(totals["reasons"]["missing_consecutive_months_or_latest_percentage"], 1)

    def test_distinct_stock_period_and_source_settings_strata_with_zero_samples(self):
        make_run(self.root, 1, value=10, symbols=["1000", "1001"])
        make_run(self.root, 2, value=42)
        make_run(self.root, 3, value=42, source="different")
        make_run(self.root, 4, value=42, config={"revenue_yoy_pct": 45})
        report = self.report()
        groups = [g for g in report["definition_groups"] if g["rule_id"] == "revenue_yoy"]
        self.assertEqual(sorted(g["saved"]["total"] for g in groups), [1, 1, 1, 2])
        fixture, = [group for group in groups if group["saved"]["total"] == 2]
        self.assertEqual(fixture["first_saved"]["total"], 1)
        case, = [c for c in report["cases"] if c["definition_id"] == fixture["definition_id"]]
        self.assertEqual(case["target_period"], "2020-07-31")
        self.assertEqual((case["saved"]["not_triggered"], case["saved"]["triggered"]), (1, 1))
        empty = self.report(filename="empty.json", cutoff="2019-08-01T00:00:00Z")
        self.assertTrue(all(r["saved"]["total"] == 0 for r in empty["rules"].values()))
        self.assertEqual(empty["scope_status"], "no_saved_run_by_cutoff")

    def test_legacy_saved_alerts_survive_missing_snapshot_metadata(self):
        from local.research_history import canonical
        first = make_run(self.root, 1)
        make_run(self.root, 2)
        directory = self.root / "runs" / first["run"]
        first.pop("research_facts")
        first["quality"].pop("snapshots")
        (directory / "research-facts.json").unlink()
        (directory / "report.json").write_bytes(canonical(first))
        report = self.report()
        legacy = report["inputs"][first["run"]]
        self.assertEqual(legacy["fact_scope"], "display_graph_only")
        self.assertEqual(legacy["raw_sources"], {})
        self.assertEqual(report["rules"]["revenue_yoy"]["saved"]["triggered"], 2)
        (directory / "alerts.json").write_bytes(b"invalid")
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            self.report(filename="broken.json")
        self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.root / "broken.json").exists())

    def test_same_save_time_conflict_cannot_choose_first_by_run_identifier(self):
        make_run(self.root, 1, value=40)
        # A separate ledger can legitimately produce a second bundle at the same wall clock time.
        (self.root / "history-1.db").rename(self.root / "first-ledger.db")
        make_run(self.root, 1, value=10)
        with contextlib.redirect_stderr(io.StringIO()) as error, self.assertRaises(SystemExit):
            self.report()
        self.assertIn("conflicting same-time", error.getvalue())
        self.assertFalse((self.root / "quality.json").exists())
