"""Synthetic source-schema fixtures. No real quotes, network or publication."""
import csv
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from local.core import ROOT
from local.market_prices import FEEDS, MAX_BYTES, NoRedirect, _date, _number, fetch, ingest, main, normalize

DAY = "2020-01-02"
WHEN = "2020-01-02T10:30:00Z"


def fixture(market="twse", rows=None, headers=None):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(headers or FEEDS[market]["columns"])
    writer.writerows(rows if rows is not None else [
        ["1090102", "1000", "虛構甲", "10.10", "12.00", "9", "11.50", "1,000", "11,500", "4"],
        ["1090102", "1001", "虛構乙", "20", "22", "19", "21", "2,000", "42,000", "8"],
    ])
    return stream.getvalue().encode("utf-8")


class ParserTests(unittest.TestCase):
    def test_twse_prices_exact_decimal_and_source(self):
        obj = normalize(fixture(), "twse", ["1000"], DAY, WHEN)
        record = obj["records"][0]
        self.assertEqual(record["close"], "11.50")
        self.assertEqual(record["volume_shares"], 1000)
        self.assertEqual(record["turnover_raw"], "11500")
        self.assertEqual(record["price_unit"], "source_reported")
        self.assertEqual(obj["source"]["dataset_id"], "11549")
        self.assertEqual(obj["universe_scope"], "explicit_symbols_not_index_membership")
        self.assertNotIn("universe_group", record)
        self.assertEqual(obj["observed_at"], "2020-01-02T10:30:00.000000+00:00")

    def test_tpex_schema_and_market_separation(self):
        obj = normalize(fixture("tpex"), "tpex", ["1001"], DAY, WHEN)
        self.assertEqual(obj["records"][0]["market"], "TPEX")
        self.assertEqual(obj["source"]["dataset_id"], "11371")

    def test_date_formats(self):
        for day in ("1090102", "20200102", "109/01/02", "2020/1/2", DAY):
            with self.subTest(day=day):
                self.assertEqual(_date(day), DAY)

    def test_invalid_dates(self):
        for day in ("1090230", "20200100", "2020-2-1", "yesterday", ""):
            with self.subTest(day=day), self.assertRaises(ValueError):
                _date(day)

    def test_missing_prices_remain_null_not_zero(self):
        body = fixture(rows=[["1090102", "1000", "虛構停牌", "--", "-", "", "N/A", "0", "0", "0"]])
        record = normalize(body, "twse", ["1000"], DAY, WHEN)["records"][0]
        self.assertEqual(record["volume_shares"], 0)
        self.assertIsNone(record["close"])
        self.assertEqual(record["missing_price_fields"], ["open", "high", "low", "close"])

    def test_missing_counts_are_not_zero(self):
        for val in ("", "--", "-", "N/A"):
            with self.subTest(val=val), self.assertRaises(ValueError):
                _number(val, integer=True)

    def test_invalid_nonnegative_numbers(self):
        for val in ("NaN", "Inf", "1,2,3", "-1", "=5+1", "1e20", "1_000", "1"*49):
            with self.subTest(val=val), self.assertRaises(ValueError):
                _number(val)

    def test_counts_cannot_be_fractional_or_overflow(self):
        for val in ("1.5", str(2**63)):
            with self.subTest(val=val), self.assertRaises(ValueError):
                _number(val, integer=True)

    def test_ohlc_range_rejected(self):
        body = fixture(rows=[["1090102", "1000", "測試", "13", "12", "9", "11", "1", "11", "1"]])
        with self.assertRaisesRegex(ValueError, "OHLC"):
            normalize(body, "twse", ["1000"], DAY, WHEN)

    def test_partial_ohlc_is_explicit(self):
        body = fixture(rows=[["1090102", "1000", "測試", "--", "12", "9", "11", "1", "11", "1"]])
        obj = normalize(body, "twse", ["1000"], DAY, WHEN)
        self.assertEqual(obj["records"][0]["missing_price_fields"], ["open"])

    def test_stale_and_mixed_date_rejected(self):
        for body, day in ((fixture(), "2020-01-01"), (fixture().replace(b"1090102,1001", b"1090101,1001"), DAY)):
            with self.subTest(day=day), self.assertRaisesRegex(ValueError, "stale/mixed"):
                normalize(body, "twse", ["1000"], day, WHEN)

    def test_future_trade_day_vs_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "later"):
            normalize(fixture(), "twse", ["1000"], "2020-01-03", WHEN)

    def test_timezone_required(self):
        with self.assertRaises(ValueError):
            normalize(fixture(), "twse", ["1000"], DAY, "2020-01-02T19:00:00")

    def test_coverage_must_match_explicit_symbols(self):
        with self.assertRaisesRegex(ValueError, "coverage incomplete"):
            normalize(fixture(), "twse", ["1000", "1002"], DAY, WHEN)

    def test_invalid_or_duplicate_requested_codes(self):
        for symbols in ([], ["TW:1000"], ["009816"], ["../../data"], ["1000", "1000"]):
            with self.subTest(symbols=symbols), self.assertRaises(ValueError):
                normalize(fixture(), "twse", symbols, DAY, WHEN)

    def test_duplicate_selected_rows(self):
        rows = list(csv.reader(io.StringIO(fixture().decode())))
        with self.assertRaisesRegex(ValueError, "duplicate symbol"):
            normalize(fixture(rows=[rows[1], rows[1]]), "twse", ["1000"], DAY, WHEN)

    def test_empty_security_name(self):
        with self.assertRaisesRegex(ValueError, "empty security"):
            normalize(fixture().replace("虛構甲".encode(), b""), "twse", ["1000"], DAY, WHEN)

    def test_header_and_row_contract(self):
        bad = [b'a,b\n1,2\n', b'a,a\n1,2\n', fixture()+b'a,b\n', fixture(headers=["日期"]*10), b'<html>denied</html>', b'{"error":true}', b'']
        for body in bad:
            with self.subTest(body=body[:20]), self.assertRaises(ValueError):
                normalize(body, "twse", ["1000"], DAY, WHEN)

    def test_bom_and_extra_source_columns(self):
        rows = list(csv.reader(io.StringIO(fixture().decode())))
        body = b'\xef\xbb\xbf' + fixture(rows=[rows[1]+["kept only in raw"]], headers=rows[0]+["來源註記"])
        self.assertEqual(len(normalize(body, "twse", ["1000"], DAY, WHEN)["records"]), 1)

    def test_unknown_feed_rejected(self):
        with self.assertRaises(ValueError):
            normalize(fixture(), "https://attacker.test", ["1000"], DAY, WHEN)


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root/"prices.db"
        self.out = self.root/"snapshots"

    def load(self, body=None, when=WHEN, **kwargs):
        return ingest(fixture() if body is None else body, "twse", ["1000", "1001"], DAY,
                      db=self.db, output=self.out, observed_at=when, acquisition="local_file_unverified", **kwargs)

    def query(self, sql):
        conn = sqlite3.connect(self.db)
        try:
            return conn.execute(sql).fetchall()
        finally:
            conn.close()

    def test_e2e_real_sqlite_and_immutable_raw(self):
        result = self.load()
        self.assertEqual(result["inserted_observations"], 2)
        self.assertEqual((self.out/result["snapshot_path"]).read_bytes(), fixture())
        report = json.loads((self.out/"latest-twse.json").read_text())
        self.assertEqual(report["acquisition"], "local_file_unverified")
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_prices_latest")[0][0], 2)
        self.assertEqual(self.query("SELECT name FROM sqlite_master WHERE name='graph_nodes'"), [])

    def test_full_file_profile_includes_unselected_rows_and_coverage(self):
        result = ingest(fixture(), "twse", ["1000"], DAY, db=self.db, output=self.out,
                        observed_at=WHEN, acquisition="local_file_unverified")
        profile = result["profile"]
        self.assertEqual(profile["columns"], list(FEEDS["twse"]["columns"]))
        self.assertEqual(profile["row_count"], 2)
        self.assertEqual(profile["date_distribution"], {DAY: 2})
        self.assertEqual(profile["selected_symbol_rows"], {"1000": 1})
        self.assertEqual(profile["missing_symbols"], [])
        self.assertEqual(profile["selected_value_validation"], "passed")
        self.assertEqual(result["bytes"], len(fixture()))
        self.assertEqual(result["http_status"], None)

    def test_same_observation_idempotent(self):
        self.load()
        self.assertEqual(self.load()["inserted_observations"], 0)
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_price_observations")[0][0], 2)

    def test_corrections_preserved_and_latest_selects_observation_time(self):
        changed = fixture().replace(b"11.50", b"11.60")
        self.load(changed, when="2020-01-03T10:30:00Z")
        self.load()  # Older observation imported later must not overwrite newer data.
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_price_observations")[0][0], 4)
        latest = self.query("SELECT record_json FROM market_prices_latest WHERE symbol='1000'")[0][0]
        self.assertEqual(json.loads(latest)["close"], "11.60")
        self.assertEqual(len(list(self.out.rglob("*.csv"))), 2)

    def test_conflicting_timestamp_rolls_back_whole_batch(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "conflicting observation"):
            self.load(fixture().replace(b"21,", b"21.5,"))
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_price_observations")[0][0], 2)
        self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)

    def test_invalid_row_creates_no_database_or_output(self):
        with self.assertRaises(ValueError):
            self.load(b'<html>blocked</html>')
        self.assertFalse(self.db.exists())
        self.assertFalse(self.out.exists())

    def test_bad_next_batch_keeps_previous_report(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        with self.assertRaises(ValueError):
            self.load(fixture().replace(b"1090102", b"1090101"))
        self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)

    def test_tampered_snapshot_rejected(self):
        result = self.load()
        (self.out/result["snapshot_path"]).write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, "immutable"):
            self.load()

    def test_source_markets_not_overwritten(self):
        self.load()
        ingest(fixture("tpex"), "tpex", ["1000"], DAY, db=self.db, output=self.out,
               observed_at=WHEN, acquisition="local_file_unverified")
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_prices_latest")[0][0], 3)

    def test_public_output_rejected(self):
        for output in (ROOT/"data/prices", ROOT, ROOT/"docs"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                ingest(fixture(), "twse", ["1000"], DAY, db=self.db, output=output,
                       observed_at=WHEN, acquisition="local_file_unverified")
        self.assertFalse(self.db.exists())

    def test_symlink_output_and_database_rejected(self):
        self.out.symlink_to(self.root/"target", target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.load()
        self.out.unlink()
        self.db.symlink_to(self.root/"target.db")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.load()

    def test_db_not_inside_snapshot_tree(self):
        self.db = self.out/"prices.db"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.load()

    def test_offline_cli_never_fetches(self):
        inp = self.root/"test.csv"
        inp.write_bytes(fixture())
        with patch('local.market_prices.fetch', side_effect=AssertionError('no network')), redirect_stdout(io.StringIO()) as log:
            main(['--market','twse','--symbols','1000','1001','--expected-date',DAY,'--input',str(inp),
                  '--db',str(self.db),'--output',str(self.out)])
        self.assertIn('no publication', log.getvalue())
        self.assertEqual(self.query("SELECT COUNT(*) FROM market_price_observations")[0][0], 2)

    def test_bad_cli_output_is_rejected_before_network(self):
        with patch('local.market_prices.fetch') as mocked, self.assertRaises(ValueError):
            main(['--market','twse','--symbols','1000','--expected-date',DAY,'--output',str(ROOT/'data')])
        mocked.assert_not_called()

    def test_cli_stale_full_file_retains_success_and_saves_failure_bytes(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        inp = self.root/"stale.csv"
        stale = fixture().replace(b"1090102,1001", b"1090101,1001")
        inp.write_bytes(stale)
        with self.assertRaises(ValueError):
            main(['--market', 'twse', '--symbols', '1000', '--expected-date', DAY,
                  '--input', str(inp), '--db', str(self.db), '--output', str(self.out)])
        self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)
        reports = list(self.out.glob('retrieval-failure-*.json'))
        self.assertEqual(len(reports), 1)
        failure = json.loads(reports[0].read_text())['failure']
        self.assertEqual(failure['stage'], 'validation_and_persistence')
        self.assertEqual(failure['profile']['date_distribution'], {'2020-01-01': 1, DAY: 1})
        self.assertEqual((self.out/failure['path']).read_bytes(), stale)
        self.assertFalse(failure['body_truncated'])

    def test_cli_invalid_selected_values_preserves_full_profile(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        inp = self.root/"invalid.csv"
        inp.write_bytes(fixture().replace(b"11.50", b"NaN"))
        with self.assertRaises(ValueError):
            main(['--market', 'twse', '--symbols', '1000', '--expected-date', DAY,
                  '--input', str(inp), '--db', str(self.db), '--output', str(self.out)])
        failure = json.loads(next(self.out.glob('retrieval-failure-*.json')).read_text())['failure']
        self.assertEqual(failure['profile']['row_count'], 2)
        self.assertEqual(failure['profile']['selected_value_validation'], 'failed')
        self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)

    def test_failed_cli_batches_preserve_success_with_structured_evidence(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        rows = list(csv.reader(io.StringIO(fixture().decode())))
        cases = {
            'missing_stock': fixture(rows=[rows[1]]),
            'missing_column': fixture().replace('收盤價'.encode(), b'unknown'),
            'duplicate_unselected': fixture(rows=[rows[1], rows[2], rows[2]]),
            'old_date': fixture().replace(b'1090102', b'1090101'),
            'negative_count': fixture().replace(b'"1,000"', b'-1'),
            'infinite_price': fixture().replace(b'11.50', b'Inf'),
            'html': b'<html>blocked</html>',
        }
        for name, body in cases.items():
            with self.subTest(name=name):
                inp = self.root/(name + '.csv')
                inp.write_bytes(body)
                prior = set(self.out.glob('retrieval-failure-*.json'))
                with self.assertRaises(ValueError):
                    main(['--market', 'twse', '--symbols', '1000', '1001', '--expected-date', DAY,
                          '--input', str(inp), '--db', str(self.db), '--output', str(self.out)])
                reports = set(self.out.glob('retrieval-failure-*.json')) - prior
                self.assertEqual(len(reports), 1)
                report = json.loads(reports.pop().read_text())
                self.assertEqual(report['status'], 'failed')
                self.assertEqual((self.out/report['failure']['path']).read_bytes(), body)
                self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)

    def test_http_failure_prefix_and_metadata_do_not_replace_success(self):
        self.load()
        before = (self.out/"latest-twse.json").read_bytes()
        with patch('local.market_prices.build_opener') as builder:
            builder.return_value.open.side_effect = HTTPError(FEEDS['twse']['resource_url'], 403,
                'Forbidden', {'Content-Type': 'text/html'}, io.BytesIO(b'<html>denied</html>'))
            with self.assertRaises(HTTPError):
                main(['--market', 'twse', '--symbols', '1000', '--expected-date', DAY,
                      '--db', str(self.db), '--output', str(self.out)])
        failure = json.loads(next(self.out.glob('retrieval-failure-*.json')).read_text())['failure']
        self.assertEqual(failure['http_status'], 403)
        self.assertEqual(failure['content_type'], 'text/html')
        self.assertEqual(failure['error_category'], 'http_error')
        self.assertEqual((self.out/failure['path']).read_bytes(), b'<html>denied</html>')
        self.assertEqual((self.out/"latest-twse.json").read_bytes(), before)


class NetworkTests(unittest.TestCase):
    def test_http_response_metadata_and_failed_response_body_are_retained(self):
        with patch('local.market_prices.build_opener') as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.headers = {'Content-Type': 'text/csv', 'Content-Length': str(len(fixture()))}
            response.status = 200
            response.geturl.return_value = FEEDS['twse']['resource_url']
            response.read.return_value = fixture()
            body = fetch('twse')
            self.assertEqual(body.metadata['http_status'], 200)
            self.assertEqual(body.metadata['content_type'], 'text/csv')
            self.assertEqual(body.metadata['response_url'], FEEDS['twse']['resource_url'])
            builder.return_value.open.side_effect = HTTPError(FEEDS['twse']['resource_url'], 403,
                'Forbidden', {'Content-Type': 'text/html'}, io.BytesIO(b'<html>denied</html>'))
            with self.assertRaises(HTTPError) as caught:
                fetch('twse')
            self.assertEqual(caught.exception.response_body, b'<html>denied</html>')
            self.assertEqual(caught.exception.response_body.metadata['http_status'], 403)

    def test_403_not_retried(self):
        with patch('local.market_prices.build_opener') as builder:
            builder.return_value.open.side_effect = HTTPError(FEEDS['twse']['resource_url'],403,'Forbidden',{},None)
            with self.assertRaises(HTTPError): fetch('twse')
            self.assertEqual(builder.return_value.open.call_count,1)

    def test_429_three_attempts_and_bounded_delay(self):
        with patch('local.market_prices.build_opener') as builder, patch('local.market_prices.time.sleep') as sleep:
            builder.return_value.open.side_effect = HTTPError(FEEDS['twse']['resource_url'],429,'Slow down',{'Retry-After':'999'},None)
            with self.assertRaises(HTTPError): fetch('twse')
            self.assertEqual(builder.return_value.open.call_count,3)
            self.assertEqual([c.args[0] for c in sleep.call_args_list],[30,30])

    def test_timeout_is_not_a_successful_empty_snapshot(self):
        with patch('local.market_prices.build_opener') as builder:
            builder.return_value.open.side_effect = TimeoutError('network unavailable')
            with self.assertRaises(TimeoutError): fetch('twse')

    def test_size_limit_and_fixed_endpoint(self):
        with patch('local.market_prices.build_opener') as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.headers = {'Content-Length': str(MAX_BYTES+1)}
            response.read.return_value = b"bounded prefix"
            with self.assertRaises(ValueError) as caught: fetch('twse')
            self.assertTrue(caught.exception.response_body.metadata["body_truncated"])
            response.read.assert_called_once_with(MAX_BYTES+1)
            url = builder.return_value.open.call_args.args[0].full_url
            self.assertEqual(url, FEEDS['twse']['resource_url'])

    def test_missing_content_length_is_bounded(self):
        with patch('local.market_prices.build_opener') as builder:
            response = builder.return_value.open.return_value.__enter__.return_value
            response.headers = {}
            response.read.return_value = fixture()
            self.assertEqual(fetch('twse'),fixture())
            response.read.assert_called_once_with(MAX_BYTES+1)

    def test_redirect_not_followed(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://elsewhere.test'))


if __name__ == '__main__':
    unittest.main()
