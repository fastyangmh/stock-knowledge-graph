"""Manifest/export contract tests. Only synthetic data and isolated SQLite."""
import copy
import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from local.core import connect, init_db, import_payload
from local.combined_universe import load_combined_universe
from local.export_json import export
from local.validate_release import validate_data_dir
from local.view_metadata import membership_summary, universe_counts

DAY = "2026-11-16"
URL = "https://example.org/synthetic-source"


def properties(ids):
    memberships = []
    for source in ids:
        memberships.append({"universe_id":source,"membership_kind":"index_constituent" if source=="TW50" else "etf_holding",
            "source_url":URL,"effective_from":DAY,"effective_to":DAY,**({"snapshot_date":DAY} if source!="TW50" else {})})
    return {"universe_ids":sorted(ids),"universe_as_of":DAY,"universe_memberships":memberships,
        "universe_group":"both" if len(ids)==2 else ("tw50_only" if ids==["TW50"] else "etf_009816_only")}


class MetadataTests(unittest.TestCase):
    def test_legacy_not_inferred(self):
        self.assertEqual(membership_summary({"id":"stock:TW:2330"}),{})
        self.assertEqual(universe_counts([{}])["unknown"],1)
    def test_summary_compact_and_valid(self):
        p=properties(["TW50","ETF:009816"])
        summary=membership_summary(p)
        self.assertEqual(summary["universe_group"],"both")
        self.assertNotIn("universe_memberships",summary)
    def test_partial_metadata_rejected(self):
        with self.assertRaises(ValueError): membership_summary({"universe_group":"both"})
    def test_group_contradiction_rejected(self):
        p=properties(["TW50"]);p["universe_group"]="both"
        with self.assertRaises(ValueError): membership_summary(p)
    def test_etf_snapshot_never_carried_forward(self):
        p=properties(["ETF:009816"]);p["universe_memberships"][0]["snapshot_date"]="2026-11-15"
        with self.assertRaises(ValueError): membership_summary(p)
    def test_unsafe_source_rejected(self):
        p=properties(["TW50"]);p["universe_memberships"][0]["source_url"]="javascript:alert(1)"
        with self.assertRaises(ValueError): membership_summary(p)
    def test_counts_overlap_not_double_counted(self):
        stocks=[membership_summary(properties(ids)) for ids in (["TW50"],["ETF:009816"],["TW50","ETF:009816"])]+[{}]
        result=universe_counts(stocks)
        self.assertEqual((result["total"],result["tw50"],result["etf_009816"],result["both"],result["unknown"]),(4,2,2,1,1))
    def test_complete_seventy_stock_real_export(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            index=root/"index.csv"; etf=root/"etf.csv"
            index.write_text("stock_id,effective_from,effective_to\n"+"".join(f"TW:{i},2026-01-01,\n" for i in range(1000,1050)))
            etf.write_text("stock_id,snapshot_date,source_url\n"+"".join(f"TW:{i},{DAY},{URL}\n" for i in range(1040,1070)))
            universe=load_combined_universe(index,etf,DAY,URL)
            payload={"stocks":[{"stock_id":sid,"ticker":sid[3:],"market":"TW","name":"Synthetic"} for sid in sorted(universe.stock_ids)]}
            with connect(root/"test.db") as conn:
                init_db(conn);import_payload(conn,universe.annotate_payload(payload))
                manifest=export(conn,root/"out",universe=universe.stock_ids,lifecycle=True)
                self.assertEqual(validate_data_dir(root/"out"),70)
                c=manifest["research_universe"]["counts"]
                self.assertEqual((c["tw50"],c["etf_009816"],c["both"],c["total"]),(50,30,10,70))
                for item in manifest["stocks"]:
                    path=root/"out"/item["path"].removeprefix("data/")
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),item["sha256"])
                    self.assertEqual(item["universe_as_of"],DAY)
    def test_tampered_hash_and_membership_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);out=root/"out"
            with connect(root/"test.db") as conn:
                init_db(conn);import_payload(conn,{"stocks":[{"stock_id":"TW:1000","ticker":"1000","market":"TW","name":"Synthetic",**properties(["TW50"])}]})
                manifest=export(conn,out)
            graph_path=out/"stocks/1000/graph.json"; original=graph_path.read_bytes()
            graph_path.write_bytes(original+b"\n")
            with self.assertRaisesRegex(ValueError,"checksum"): validate_data_dir(out)
            graph_path.write_bytes(original)
            altered=copy.deepcopy(manifest);altered["stocks"][0]["universe_group"]="both"
            (out/"manifest.json").write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,"membership"): validate_data_dir(out)
    def test_corrupt_counts_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with connect(root/"test.db") as conn:
                init_db(conn);import_payload(conn,{"stocks":[{"stock_id":"TW:1000","ticker":"1000","market":"TW","name":"Synthetic"}]})
                manifest=export(conn,root/"out")
            manifest["research_universe"]["counts"]["both"]=1
            (root/"out/manifest.json").write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,"summary"): validate_data_dir(root/"out")
