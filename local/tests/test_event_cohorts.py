"""Published descriptive cohorts through saved alerts, runs and the public report."""
import unittest

from event_fixtures import complete_bundle, event, outcome
from local.event_study import analyze
from test_event_study import ASOF, CONFIG


class EventCohortTests(unittest.TestCase):
    def test_policy_versions_separate_groups_and_preserve_first_event_identity(self):
        first = complete_bundle(alerts=True)
        default = analyze([first], ASOF)
        custom = analyze([first], ASOF, {"max_quote_gap_days": 4})
        self.assertEqual(event(default)["event_id"], event(custom)["event_id"])
        self.assertEqual(default["cohort_policy"]["version"], "event-cohorts-1")
        self.assertNotEqual(default["cohort_policy"]["settings_id"], custom["cohort_policy"]["settings_id"])
        for report in (default, custom):
            groups = report["categories"]["price_volume"]["summaries"]
            self.assertTrue(all(g["settings_id"] == report["cohort_policy"]["settings_id"] for g in groups))
        ids = {g["group_id"] for g in default["categories"]["price_volume"]["summaries"]}
        self.assertTrue(ids.isdisjoint(g["group_id"] for g in custom["categories"]["price_volume"]["summaries"]))

    def test_distinct_same_stock_capture_windows_overlap_duplicates_have_run_evidence(self):
        first = complete_bundle(alerts=True)
        repeat = complete_bundle(2, alerts=True, completed="2020-08-16T08:00:00+08:00")
        later = complete_bundle(3, "2020-08-17", close="115")
        result = analyze([first, repeat, later], ASOF, CONFIG)
        e = event(result)
        self.assertEqual(e["repeat_runs"], [repeat.report["run"]])
        self.assertEqual(result["counts"]["events"], 6)
        row = outcome(result)
        window = row["followup_window"]
        self.assertEqual(window["start_at"], e["event_at"])
        self.assertEqual(window["end_at"], row["followup"]["captured_at"])
        self.assertEqual(window["same_stock_overlapping_events"], 5)
        self.assertFalse(window["right_censored"])
        short = analyze([first, repeat, later], "2020-08-16T22:00:00+08:00", CONFIG)
        window = outcome(short)["followup_window"]
        self.assertEqual(window["end_at"], short["analysis_at"])
        self.assertTrue(window["right_censored"])
        self.assertEqual(outcome(short, metric="revenue_yoy_change_pp")["followup_window"]["right_censored"], True)
        missing = outcome(result, metric="revenue_yoy_change_pp")
        self.assertEqual(missing["reason"], "target_month_not_saved_no_nearest_month_fill")
        self.assertFalse(missing["followup_window"]["right_censored"])

    def test_zero_observed_groups_trace_reason_and_censoring_to_events(self):
        first = complete_bundle(alerts=True)
        result = analyze([first], "2020-08-16T20:00:00+08:00")
        for group in result["categories"]["price_volume"]["summaries"]:
            self.assertEqual(group["n_observed"], 0)
            self.assertIsNone(group["statistics"])
            self.assertEqual(list(group["unavailable_by_reason"].values()), [group["events"]])
            member = next(e for e in result["categories"]["price_volume"]["events"]
                          if e["event_id"] == group["events"][0])
            row = next(r for r in member["outcomes"] if r["metric"] == group["metric"] and r["horizon"] == group["horizon"])
            self.assertIn(row["reason"], group["unavailable_by_reason"])
            self.assertEqual(group["n_right_censored"], int(row["followup_window"]["right_censored"]))
            self.assertEqual(row["group_id"], group["group_id"])

    def test_audited_empty_sample_keeps_selection_and_saved_coverage_at_cutoff(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from local.event_study import build
        from test_event_integration import research_run
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            research_run(root, 0, '2020-08-14', '100', 1000)
            research_run(root, 1, '2020-08-15', '110', 3000, alerts=True)
            report = build(root/'runs', '2020-08-14T23:00:00+08:00')
            self.assertEqual(report["counts"]["events"], 0)
            selected, = report["inputs"]
            self.assertEqual(selected["selection"]["mode"], "explicit_symbols")
            self.assertEqual(selected["selection"]["stock_ids"], ["TW:1000"])
            self.assertEqual(selected["saved_periods"]["market"]["TWSE"],
                             {"first":"2020-08-14", "last":"2020-08-14", "distinct_dates":1})
            self.assertEqual(report["categories"]["price_volume"]["summaries"], [])
            self.assertEqual(report["counts"]["runs_after_cutoff"], 1)
            empty = build(root/'runs', '2019-01-01T00:00:00Z')
            self.assertEqual(empty["inputs"], [])
            self.assertEqual(empty["counts"]["runs_after_cutoff"], 2)

    def test_split_like_raw_drop_keeps_unadjusted_basis_and_interval_coverage_unknown(self):
        first = complete_bundle(alerts=True, close="100")
        future = complete_bundle(2, "2020-08-16", close="50")
        row = outcome(analyze([first, future], ASOF))
        self.assertEqual(row["value"], "-50.000000")
        self.assertIn("split_reverse_split", row["unknown_action_coverage"])
        self.assertEqual(row["basis"]["price_basis"], "source_unadjusted")
        next(f for f in future.facts["facts"] if f["kind"]=="market_price")["price_basis"]="split_adjusted"
        row = outcome(analyze([first, future], ASOF))
        self.assertEqual(row["reason"], "quote_source_or_basis_changed")
        self.assertIsNone(row["value"])

    def test_window_closes_when_all_quotes_through_position_have_been_saved(self):
        first = complete_bundle(alerts=True)
        early_capture = complete_bundle(2, "2020-08-17", close="120")
        late_period = complete_bundle(3, "2020-08-16", close="108", completed="2020-08-18T22:00:00+08:00")
        before = analyze([first, early_capture, late_period], "2020-08-17T23:00:00+08:00", CONFIG)
        self.assertEqual(outcome(before)["target_period"], "2020-08-17")
        self.assertTrue(outcome(before, horizon=2)["followup_window"]["right_censored"])
        after = analyze([first, early_capture, late_period], ASOF, CONFIG)
        row = outcome(after, horizon=2)
        self.assertEqual(row["followup"]["run"], early_capture.report["run"])
        self.assertEqual(row["followup_window"]["end_at"], "2020-08-18T14:00:00+00:00")

    def test_tied_first_triggers_cannot_choose_conflicting_market_baseline_by_run_name(self):
        a = complete_bundle(1, alerts=True, close="100")
        b = complete_bundle(2, alerts=True, close="90")
        with self.assertRaisesRegex(ValueError, "conflicting same-time event baseline"):
            analyze([a,b], ASOF)
        matching = complete_bundle(3, alerts=True, close="100")
        result = analyze([a,matching], ASOF)
        self.assertEqual(result["counts"]["duplicate_period_events_suppressed"], 6)

    def test_cross_period_same_stock_overlaps_depend_on_horizon_and_cutoff(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from local.event_study import build
        from test_event_integration import research_run
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for n, (day, close, alerted) in enumerate([
                ("2020-08-14","100",False), ("2020-08-15","120",True),
                ("2020-08-16","121",False), ("2020-08-17","150",True),
                ("2020-08-18","152",False)
            ]):
                research_run(root,n,day,close,1000,alerts=alerted,cap=0)
            report = build(root/'runs', ASOF, config=CONFIG)
            events = [e for e in report["categories"]["price_volume"]["events"] if e["rule_id"]=="price_change"]
            self.assertEqual([e["target_period"] for e in events], ["2020-08-15","2020-08-17"])
            first, later = events
            a = {o["horizon"]:o for o in first["outcomes"] if o["metric"]=="close_change_pct"}
            b = {o["horizon"]:o for o in later["outcomes"] if o["metric"]=="close_change_pct"}
            self.assertLess(a[1]["followup_window"]["end_at"], later["event_at"])
            self.assertEqual(a[2]["followup_window"]["end_at"], later["event_at"])
            self.assertEqual(b[1]["followup_window"]["same_stock_overlapping_events"], 0)
            self.assertGreaterEqual(b[2]["followup_window"]["same_stock_overlapping_events"], 1)
            self.assertEqual(a[1]["group_id"], b[1]["group_id"])
            group = next(g for g in report["categories"]["price_volume"]["summaries"] if g["group_id"]==a[2]["group_id"])
            self.assertEqual((group["n_total"],group["n_observed"],group["n_right_censored"]), (2,1,1))
            self.assertEqual(group["unavailable_by_reason"][b[2]["reason"]], [later["event_id"]])

    def test_original_summary_reader_accepts_saved_events_without_cohort_extension(self):
        from local.event_study import summarize
        e = event(analyze([complete_bundle(alerts=True)], ASOF))
        e.pop("settings_id")
        for r in e["outcomes"]:
            r.pop("followup_window")
            r.pop("group_id")
        groups = summarize([e])
        self.assertTrue(all(g["n_total"]==1 and "settings_id" not in g and "n_right_censored" not in g for g in groups))
