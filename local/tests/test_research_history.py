"""Synthetic as-recorded history tests; never real prices, investments or API IO."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch
from local.research_history import record_snapshot, replay, validate_payload, strict_json, validate_symbols

T0 = "2020-01-02T08:00:00+00:00"
T1 = "2020-01-02T09:00:00+00:00"
T2 = "2020-01-03T08:00:00+00:00"
T3 = "2020-01-04T08:00:00+00:00"


def payload(observed=T0, value=1000):
    return {"stocks":[{"stock_id":"TW:1000","ticker":"1000","market":"TW","name":"Synthetic A"},
                      {"stock_id":"TW:1001","ticker":"1001","market":"TW","name":"Synthetic B"}],
            "sources":[{"source_id":"synthetic","provider":"Synthetic source","url":"https://example.org/fixture","license_type":"synthetic-only"}],
            "documents":[{"document_id":"d1","source_id":"synthetic","doc_type":"financial","title":"Synthetic monthly report",
                "content":str(value),"stock_ids":["TW:1000"],"published_at":observed,"available_at":observed,"period_end":"2019-12-31"}],
            "financial_metrics":[{"stock_id":"TW:1000","source_id":"synthetic","metric":"monthly_revenue","period_end":"2019-12-31",
                "period_type":"month","value":value,"unit":"source_reported","available_at":observed}],
            "chip_metrics":[],"metadata":{"observed_at":observed}}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
    def register(self,p,recorded=T1):
        with patch("local.research_history.utc_now",return_value=recorded):
            return record_snapshot(self.conn,p)
    def read(self,when=T3,ids=None):
        with patch("local.research_history.utc_now",return_value=T3):
            return replay(self.conn,ids or {"TW:1000"},when)
    def test_idempotent_snapshot_preserves_first_registration(self):
        first=self.register(payload())
        second=self.register(payload(),T2)
        self.assertTrue(first["inserted"]);self.assertFalse(second["inserted"])
        self.assertEqual(first["recorded_at"],second["recorded_at"])
        self.assertEqual(self.conn.execute("SELECT count(*) FROM research_snapshots").fetchone()[0],1)
    def test_revision_append_and_cutoff(self):
        self.register(payload());self.register(payload(T2,1500),T2)
        before,_=self.read(T1);after,_=self.read(T3)
        self.assertEqual(before["financial_metrics"][0]["value"],1000)
        self.assertEqual(after["financial_metrics"][0]["value"],1500)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM research_snapshots").fetchone()[0],2)
    def test_backfilled_data_was_not_known_before_local_registration(self):
        self.register(payload(T0),T2)
        with self.assertRaisesRegex(ValueError,"coverage"): self.read(T1)
    def test_late_old_snapshot_does_not_replace_newer_observation(self):
        self.register(payload(T2,1500),T2);self.register(payload(T0,1000),T3)
        selected,_=self.read()
        self.assertEqual(selected["financial_metrics"][0]["value"],1500)
    def test_same_time_conflict_is_not_arbitrarily_chosen(self):
        self.register(payload(T0,1000),T1);self.register(payload(T0,1500),T2)
        with self.assertRaisesRegex(ValueError,"conflicting same-time"): self.read()
    def test_same_fact_different_input_metadata_not_false_conflict(self):
        self.register(payload());other=payload();other["metadata"]["note"]="reimport"
        self.register(other,T2);result,_=self.read()
        self.assertEqual(result["financial_metrics"][0]["value"],1000)
    def test_future_observation_rejected(self):
        with self.assertRaisesRegex(ValueError,"future"): self.register(payload(T3),T1)
    def test_metric_sources_require_reconciliation(self):
        self.register(payload())
        second=payload(T2);second['sources'].append({'source_id':'other','provider':'Other'})
        second['financial_metrics'][0]['source_id']='other';self.register(second,T2)
        with self.assertRaisesRegex(ValueError,'reconciliation'):self.read()
    def test_document_future_availability_not_used(self):
        data=payload();data['documents'][0]['available_at']=T3
        self.register(data);selected,_=self.read(T1)
        self.assertEqual(selected['documents'],[])
    def test_document_links_are_clipped_to_selected_stocks(self):
        data=payload();data['documents'][0]['stock_ids']=['TW:1000','TW:1001'];self.register(data)
        selected,_=self.read()
        self.assertEqual(selected['documents'][0]['stock_ids'],['TW:1000'])
        self.assertEqual(len(selected['stocks']),1)
    def test_latest_document_link_removal_removes_old_research_edge(self):
        self.register(payload())
        other=payload(T2)
        other['documents'][0]['stock_ids']=['TW:1001']
        self.register(other,T2)
        result,_=self.read()
        self.assertEqual(result['documents'],[])
    def test_tampered_payload_detected(self):
        self.register(payload());self.conn.execute("UPDATE research_snapshots SET payload_json='{}'")
        with self.assertRaisesRegex(ValueError,'checksum'):self.read()
    def test_tampered_metadata_timestamp_detected(self):
        self.register(payload());self.conn.execute("UPDATE research_snapshots SET observed_at=?",(T1,))
        with self.assertRaisesRegex(ValueError,'timestamp'):self.read()
    def test_missing_metric_source_is_not_guessed(self):
        data=payload();data['financial_metrics'][0].pop('source_id')
        with self.assertRaisesRegex(ValueError,'source_id'):validate_payload(data)
    def test_missing_observed_time_is_not_invented(self):
        data=payload();data.pop('metadata')
        with self.assertRaisesRegex(ValueError,'observed_at'):validate_payload(data)
    def test_no_input_mutation(self):
        data=payload();before=copy.deepcopy(data);self.register(data);self.read()
        self.assertEqual(data,before)
    def test_invalid_input_contracts(self):
        variants=[]
        for value in (True,float('nan'),float('inf'),'1000'):
            data=payload();data['financial_metrics'][0]['value']=value;variants.append(data)
        data=payload();data['stocks'][0]['ticker']='9999';variants.append(data)
        data=payload();data['stocks'].append(data['stocks'][0]);variants.append(data)
        data=payload();data['documents'][0]['stock_ids']=['TW:9999'];variants.append(data)
        data=payload();data['financial_metrics']*=2;variants.append(data)
        for data in variants:
            with self.subTest(data=data),self.assertRaises(ValueError):validate_payload(data)
    def test_taipei_period_boundary(self):
        data=payload('2020-01-01T00:00:00+08:00')
        data['financial_metrics'][0]['period_end']='2020-01-01'
        validate_payload(data)
    def test_strict_json_duplicates_and_nonfinite(self):
        for body in (b'[]',b'{"a":1,"a":2}',b'{"a":NaN}',b''):
            with self.subTest(body=body),self.assertRaises(ValueError):strict_json(body)
    def test_symbols_are_explicit_and_bounded(self):
        self.assertEqual(validate_symbols(['1000']),{'TW:1000'})
        for symbols in ([],['1000','1000'],['CASH'],['009816'],[True]):
            with self.subTest(symbols=symbols),self.assertRaises(ValueError):validate_symbols(symbols)
    def test_history_remains_caller_transactional(self):
        self.conn.execute('BEGIN');self.register(payload());self.conn.rollback()
        self.assertEqual(self.conn.execute("SELECT count(*) FROM sqlite_master WHERE name='research_snapshots'").fetchone()[0],0)
