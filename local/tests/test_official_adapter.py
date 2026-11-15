"""Synthetic fixtures with official field names; no real market data or network."""
import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from local.core import ROOT, connect, init_db, import_payload
from local.collect_official import download, fetch_csv
from local.official_adapter import csv_rows, number, month_end, normalize_records, from_snapshots
from local.source_registry import load_approved
from local.export_json import export
from local.validate_release import validate_data_dir
from urllib.error import HTTPError

REGISTRY=ROOT/'local/official_datasets.json'
SOURCES=load_approved(REGISTRY)
COMPANY='出表日期,公司代號,公司名稱,公司簡稱,產業別\n1151115,2330,測試公司股份有限公司,測試公司,24\n'.encode()
REVENUE='出表日期,資料年月,公司代號,公司名稱,營業收入-當月營收,營業收入-上月比較增減(%),營業收入-去年同月增減(%)\n1151115,11510,2330,測試公司,1000,0,-10.5\n'.encode()
WHEN='2026-11-15T08:00:00+00:00'


def fixtures():
    return [(SOURCES[0],csv_rows(COMPANY),WHEN),(SOURCES[1],csv_rows(REVENUE),WHEN)]

class AdapterTests(unittest.TestCase):
    def test_parse_roc_gregorian_and_leap_month(self):
        self.assertEqual(month_end('11302'),'2024-02-29')
        self.assertEqual(month_end('202610'),'2026-10-31')
        with self.assertRaises(ValueError):month_end('11513')
    def test_zero_missing_commas_and_nonfinite(self):
        self.assertEqual(number('0'),0);self.assertIsNone(number('--'));self.assertEqual(number('1,234.5'),1234.5)
        for value in ('NaN','Infinity','=1+2','abc'):
            with self.assertRaises(ValueError):number(value)
    def test_bad_csv_rejected(self):
        for body in (b'<html>denied</html>',b'a,a\n1,2\n',b'a,b\n1,2,3\n',b'a,b\n'):
            with self.assertRaises(ValueError):csv_rows(body)
    def test_bom_csv(self):
        self.assertEqual(csv_rows(b'\xef\xbb\xbf'+COMPANY)[0]['公司代號'],'2330')
    def test_no_backdating_availability(self):
        payload=normalize_records(fixtures(),{'TW:2330'},as_of='2026-11-15')
        self.assertEqual(payload['documents'][0]['available_at'],WHEN)
        self.assertEqual(payload['financial_metrics'][0]['period_end'],'2026-10-31')
        self.assertTrue(all(m['available_at']==WHEN for m in payload['financial_metrics']))
    def test_coverage_incomplete_fails(self):
        with self.assertRaisesRegex(ValueError,'coverage'):
            normalize_records(fixtures(),{'TW:2330','TW:2454'},as_of='2026-11-15')
    def test_incorrect_historical_as_of_fails(self):
        with self.assertRaises(ValueError):normalize_records(fixtures(),{'TW:2330'},as_of='2025-11-15')
    def test_future_report_date_fails(self):
        data=fixtures();data[0][1][0]['出表日期']='1151116'
        with self.assertRaises(ValueError):normalize_records(data,{'TW:2330'},as_of='2026-11-15')
    def test_duplicate_period_fails(self):
        data=fixtures();data[1][1].append(copy.deepcopy(data[1][1][0]))
        with self.assertRaises(ValueError):normalize_records(data,{'TW:2330'},as_of='2026-11-15')
    def test_required_schema_change_fails(self):
        data=fixtures();data[1][1][0].pop('資料年月')
        with self.assertRaises(ValueError):normalize_records(data,{'TW:2330'},as_of='2026-11-15')
    def test_missing_revenue_not_zero(self):
        data=fixtures();data[1][1][0]['營業收入-當月營收']='--'
        with self.assertRaisesRegex(ValueError,'coverage'):normalize_records(data,{'TW:2330'},as_of='2026-11-15')
    def test_snapshot_to_sqlite_to_graph_e2e(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with patch('local.collect_official.fetch_csv',side_effect=[COMPANY,REVENUE]),patch('local.collect_official.now',return_value=WHEN),patch('local.collect_official.time.sleep'):
                result=download(REGISTRY,root/'snapshots')
            self.assertEqual(len(result),2)
            payload=from_snapshots(root/'snapshots',REGISTRY,{'TW:2330'},as_of='2026-11-15')
            with connect(root/'test.db') as conn:
                init_db(conn);import_payload(conn,payload)
                manifest=export(conn,root/'out',universe={'TW:2330'},lifecycle=True)
                self.assertEqual(validate_data_dir(root/'out'),1)
                self.assertEqual(len(manifest['sources']),2)
                graph=json.loads((root/'out/stocks/2330/graph.json').read_text())
                self.assertTrue(any(n.get('license_url')=='https://data.gov.tw/license' for n in graph['nodes']))
                self.assertTrue(any(n.get('attribution') for n in graph['nodes']))
            file=root/'snapshots'/result[0]['path'];file.write_bytes(file.read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'checksum'):from_snapshots(root/'snapshots',REGISTRY,{'TW:2330'},as_of='2026-11-15')
    def test_failed_batch_preserves_previous_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);old=root/'retrieval_manifest.json';old.write_text('previous')
            with patch('local.collect_official.fetch_csv',side_effect=[COMPANY,OSError('network failure')]),patch('local.collect_official.time.sleep'):
                with self.assertRaises(OSError):download(REGISTRY,root)
            self.assertEqual(old.read_text(),'previous')
    def test_empty_registry_is_not_success(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'registry.json';path.write_text('[]')
            with self.assertRaises(ValueError):download(path,Path(d)/'out')
    def test_403_is_not_retried(self):
        error=HTTPError(SOURCES[0]['resource_url'],403,'forbidden',{},None)
        with patch('local.collect_official.build_opener') as build:
            build.return_value.open.side_effect=error
            with self.assertRaises(HTTPError):fetch_csv(SOURCES[0]['resource_url'])
            self.assertEqual(build.return_value.open.call_count,1)
    def test_429_retries_are_bounded(self):
        error=HTTPError(SOURCES[0]['resource_url'],429,'rate limit',{'Retry-After':'2'},None)
        with patch('local.collect_official.build_opener') as build,patch('local.collect_official.time.sleep') as sleep:
            build.return_value.open.side_effect=error
            with self.assertRaises(HTTPError):fetch_csv(SOURCES[0]['resource_url'])
            self.assertEqual(build.return_value.open.call_count,3);self.assertEqual(sleep.call_count,2)

    def test_trimmed_duplicate_headers_are_rejected(self):
        with self.assertRaises(ValueError):csv_rows(b'a, a\n1,2\n')
    def test_invalid_thousands_separator_grouping(self):
        for value in ('1,2,3','12,34','1,000,00'):
            with self.assertRaises(ValueError):number(value)
    def test_fifty_synthetic_issuers_semantic_cache_and_export(self):
        # These are fabricated issuer IDs, not the Taiwan 50 constituent list.
        from local.semantic import compute_semantic
        company_rows=[];revenue_rows=[]
        universe={f'TW:{2000+i}' for i in range(50)}
        for i in range(50):
            company_rows.append({'出表日期':'1151115','公司代號':str(2000+i),'公司名稱':f'Synthetic {i}'})
            revenue_rows.append({'出表日期':'1151115','公司代號':str(2000+i),'公司名稱':f'Synthetic {i}',
                                 '資料年月':'11510','營業收入-當月營收':str(1000+i)})
        payload=normalize_records([(SOURCES[0],company_rows,WHEN),(SOURCES[1],revenue_rows,WHEN)],universe,as_of='2026-11-15')
        class Encoder:
            def get_embedding_dimension(self):return 3
            def encode(self,texts,batch_size=32):return [[1,1,1] for _ in texts]
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            with connect(root/'test.db') as conn:
                init_db(conn);import_payload(conn,payload)
                first=compute_semantic(conn,model_name='test/synthetic',revision='test-v1',encoder=Encoder(),as_of=WHEN)
                self.assertEqual(first['encoded'],50)
                self.assertEqual(first['pairs_evaluated'],1225)
                with patch('local.semantic.load_encoder',side_effect=AssertionError('no model reload')):
                    second=compute_semantic(conn,model_name='test/synthetic',revision='test-v1',as_of=WHEN)
                self.assertEqual(second['cache_hits'],50)
                self.assertTrue(second['graph_reused'])
                export(conn,root/'out',universe=universe,lifecycle=True)
                self.assertEqual(validate_data_dir(root/'out'),50)
