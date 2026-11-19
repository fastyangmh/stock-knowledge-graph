"""Synthetic explicit price notices, using private CLI, raw bytes and SQLite."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from local.market_graph import read_prices
from local.market_prices import ingest, main, normalize
from local.research_history import canonical
from test_market_graph import CSV, DAY
from test_research_history import T1, T2, T3

T4 = '2020-01-05T08:00:00+00:00'
T5 = '2020-01-06T08:00:00+00:00'
FIXED = CSV.replace(b'11.00,1000', b'11.50,1000')


def sha(body):
    return hashlib.sha256(body).hexdigest()


class MarketNoticeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db, self.raw = self.root/'prices.db', self.root/'prices'
        ingest(CSV, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T1, acquisition='local_file_unverified')

    def notice(self, action='correct', *, published=T2, target=CSV, replacement=FIXED, parent=None, symbol='1000'):
        evidence = f'Synthetic exchange notice {action} {symbol} {DAY} {published}'.encode()
        (self.root/'notice.txt').write_bytes(evidence)
        return dict(schema_version='market-notice-1.0', action=action, market='twse',
                    source_id='twse_daily_11549', symbol=symbol, trade_date=DAY,
                    published_at=published, effective_at=published, observed_at=published,
                    target_raw_sha256=sha(target), parent_notice_sha256=parent,
                    target_record_sha256=sha(canonical(normalize(target, 'twse', [symbol], DAY, T1)['records'][0])),
                    replacement_raw_sha256=sha(replacement) if replacement else None,
                    evidence_url='https://www.twse.com.tw/zh/notice/example',
                    evidence_sha256=sha(evidence), locator='Synthetic notice, line 1')

    def register(self, notice, *, recorded=T3, replacement=FIXED, symbol='1000'):
        path = self.root/'notice.json'
        path.write_text(json.dumps(notice))
        args = ['--market', 'twse', '--symbols', symbol, '--expected-date', DAY,
                '--notice', str(path), '--notice-evidence', str(self.root/'notice.txt'),
                '--db', str(self.db), '--output', str(self.raw)]
        if replacement is not None:
            path = self.root/'replacement.csv'
            path.write_bytes(replacement)
            args.extend(['--input', str(path)])
        with patch('local.market_notices.utc_now', return_value=recorded):
            main(args)

    def read(self, cutoff):
        return read_prices(self.db, 'twse', ['1000'], DAY, cutoff, self.raw)

    def test_late_duplicate_leaves_distinct_revision_eligible_for_its_notice(self):
        for body, when in [(FIXED, T2), (CSV, T3)]:
            ingest(body, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
                   observed_at=when, acquisition='local_file_unverified')
        self.assertEqual([self.read(t)[0]['raw_sha256'] for t in (T1, T2, T3)],
                         [sha(CSV), sha(FIXED), sha(FIXED)])
        with self.assertRaisesRegex(ValueError, 'stale'):
            self.register(self.notice(published=T3, target=CSV), recorded=T4)
        self.register(self.notice('withdraw', published=T3, target=FIXED, replacement=None),
                      recorded=T4, replacement=None)
        self.assertEqual(self.read(T4), [])

    def test_same_raw_retrieved_after_notice_observation_can_still_be_targeted(self):
        ingest(CSV, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T3, acquisition='local_file_unverified')
        self.register(self.notice(published=T2), recorded=T4)
        self.assertEqual(self.read(T4)[0]['raw_sha256'], sha(FIXED))

    def test_correction_visible_only_after_actual_local_registration(self):
        notice = self.notice()
        self.register(notice)
        self.register(notice, recorded=T4)
        self.assertEqual(self.read(T2)[0]['record']['close'], '11.00')
        current = self.read(T3)[0]
        self.assertEqual((current['record']['close'], current['recorded_at']), ('11.50', T3))
        self.assertEqual(current['raw_sha256'], sha(FIXED))

    def test_withdrawal_and_republication_audited_without_rewriting_first_saved_event(self):
        from local.bundle_audit import audit_bundle
        from local.event_study import analyze
        from local.research import run
        from local.research_history import canonical
        from test_research_history import payload
        (self.root/'input.json').write_bytes(canonical(payload()))
        prior_day = '2020-01-01'
        prior = CSV.replace(b'20200102', b'20200101').replace(b'11.00,1000', b'9.00,1000')
        ingest(prior, 'twse', ['1000'], prior_day, db=self.db, output=self.raw,
               observed_at=T1, acquisition='local_file_unverified')
        def bundle(cutoff):
            with patch('local.research.utc_now', return_value=cutoff), patch('local.research_history.utc_now', return_value=cutoff):
                report = run(self.root/'input.json', ['1000'], history_db=self.root/'history.db',
                             output_root=self.root/'runs', known_at=cutoff, alerts=True,
                             price_snapshots=self.raw, prices_db=self.db, trade_date=DAY)
            return audit_bundle(self.root/'runs', report['run'])
        first = bundle(T1)
        correction = self.notice()
        self.register(correction, recorded=T2)
        second = bundle(T2)
        ck = sha(canonical(correction))
        price = next(f for f in second.facts['facts'] if f.get('trade_date') == DAY)
        self.assertEqual((price['notice_sha256'], price['recorded_at'], price['recorded_at_status']), (ck, T2, 'known'))
        withdrawal = self.notice('withdraw', target=FIXED, replacement=None, parent=ck, published=T3)
        self.register(withdrawal, recorded=T3, replacement=None)
        third = bundle(T3)
        self.assertFalse(any(f.get('trade_date') == DAY for f in third.facts['facts']))
        self.assertEqual(third.report['counts']['market_nodes'], 0)
        for result in third.alerts['stocks']['TW:1000']['categories']['price_volume']:
            self.assertEqual(result['reason'], 'target_price_missing_at_cutoff')
        self.assertEqual(third.report['quality']['market_notices'][-1]['notice']['action'], 'withdraw')
        # An ordinary later retrieval of the old file cannot restore a withdrawn quote.
        ingest(CSV, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T4, acquisition='local_file_unverified')
        self.assertEqual(self.read(T4), [])
        republish = self.notice('republish', target=FIXED, parent=sha(canonical(withdrawal)), published=T4)
        self.register(republish, recorded=T5)
        fourth = bundle(T5)
        self.assertEqual(next(f for f in fourth.facts['facts'] if f.get('trade_date') == DAY)['close'], '11.50')
        old = audit_bundle(self.root/'runs', first.report['run'])
        self.assertEqual(old.report_sha256, first.report_sha256)
        report = analyze([first, second, third, fourth], T5)
        events = report['categories']['price_volume']['events']
        third_input = next(b for b in report['inputs'] if b['run'] == third.report['run'])
        self.assertEqual([(m['action'],m['notice_sha256']) for m in third_input['market_notices']],
                         [('correct',ck),('withdraw',sha(canonical(withdrawal)))])
        self.assertEqual(third_input['market_notices'][-1]['recorded_at'], T3)
        early = analyze([first, second, third, fourth], T1)
        self.assertEqual(early['inputs'][0]['market_notices'], [])
        self.assertEqual([(e['baseline']['market']['close'], e['baseline']['market']['raw_sha256']) for e in events],
                         [('11.00', sha(CSV))])

    def test_cutoff_cli_shows_pending_withdrawal_then_its_activation(self):
        from contextlib import redirect_stdout
        from io import StringIO
        notice = self.notice('withdraw', replacement=None)
        notice['effective_at'] = T5
        self.register(notice, replacement=None)
        def inspect(known):
            stream = StringIO()
            with redirect_stdout(stream):
                main(['--market', 'twse', '--symbols', '1000', '--expected-date', DAY,
                      '--known-at', known, '--db', str(self.db), '--output', str(self.raw)])
            return json.loads(stream.getvalue())
        early = inspect(T2)
        self.assertEqual(early['notices'], [])
        pending = inspect(T4)
        self.assertEqual(pending['notices'][0]['status'], 'pending_effective')
        self.assertEqual(pending['observations'][0]['record']['close'], '11.00')
        late = inspect(T5)
        self.assertEqual(late['notices'][0]['status'], 'withdrawn')
        self.assertEqual(late['observations'], [])

    def audited(self, cutoff, symbols=('1000',)):
        from local.bundle_audit import audit_bundle
        from local.research import run
        from test_research_history import payload
        (self.root/'input.json').write_bytes(canonical(payload()))
        with patch('local.research.utc_now', return_value=cutoff), patch('local.research_history.utc_now', return_value=cutoff):
            report = run(self.root/'input.json', list(symbols), history_db=self.root/'history.db',
                         output_root=self.root/'runs', known_at=cutoff, alerts=True,
                         prices_db=self.db, price_snapshots=self.raw, trade_date=DAY)
        return audit_bundle(self.root/'runs', report['run'])

    def test_pending_notice_keeps_ordinary_update_until_activation_in_audited_research(self):
        notice = self.notice()
        notice['effective_at'] = T5
        self.register(notice)
        update = CSV.replace(b'11.00,1000', b'11.25,1000')
        ingest(update, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T4, acquisition='https_download')
        for when, close in [(T3, '11.00'), (T4, '11.25'), (T5, '11.50')]:
            with self.subTest(when=when):
                self.assertEqual(self.read(when)[0]['record']['close'], close)
                bundle = self.audited(when)
                fact, = (f for f in bundle.facts['facts'] if f['kind'] == 'market_price')
                self.assertEqual(fact['close'], close)

    def test_pending_observation_must_match_ordinary_record_even_after_rehash(self):
        from local.bundle_audit import audit_bundle
        notice = self.notice('withdraw', replacement=None)
        notice['effective_at'] = T5
        self.register(notice, replacement=None)
        update = CSV.replace(b'11.00,1000', b'11.25,1000')
        ingest(update, 'twse', ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T4, acquisition='https_download')
        bundle = self.audited(T4)
        path = self.root/'runs'/bundle.report['run']
        fact = next(f for f in bundle.facts['facts'] if f['kind'] == 'market_price')
        fact['high'] = '11.99'
        body = canonical(bundle.facts)
        (path/'research-facts.json').write_bytes(body)
        bundle.report['research_facts'].update(sha256=sha(body), size_bytes=len(body))
        (path/'report.json').write_bytes(canonical(bundle.report))
        with self.assertRaisesRegex(ValueError, 'pending market notice'):
            audit_bundle(self.root/'runs', bundle.report['run'])

    def test_rehashed_graph_alert_and_acquisition_must_match_replacement_evidence(self):
        from copy import deepcopy
        from local.bundle_audit import audit_bundle
        self.register(self.notice())
        original = self.audited(T3)
        sid = 'TW:1000'
        path = self.root/'runs'/original.report['run']
        for part, field, value in [
                ('graph', 'high', '11.99'), ('graph', 'price_unit', 'invented'),
                ('graph', 'recorded_at', T1), ('alert', 'volume_unit', 'invented'),
                ('alert', 'available_at', T1), ('fact', 'acquisition', 'https_download')]:
            with self.subTest(part=part, field=field):
                report, manifest = deepcopy(original.report), deepcopy(original.manifest)
                facts, alerts, graph = deepcopy(original.facts), deepcopy(original.alerts), deepcopy(original.graphs[sid])
                ref = alerts['stocks'][sid]['categories']['price_volume'][0]
                node = next(n for n in graph['nodes'] if n['type'] == 'market_price')
                fact = next(f for f in facts['facts'] if f['kind'] == 'market_price')
                if part == 'graph':
                    node[field] = value
                elif part == 'alert':
                    ref['evidence'][0][field] = value
                else:
                    fact[field] = node[field] = report['market_observations'][0][field] = value
                    for check in alerts['stocks'][sid]['categories']['price_volume']:
                        check['evidence'][0][field] = value
                for check in alerts['stocks'][sid]['categories']['price_volume']:
                    check.pop('id')
                    check['id'] = sha(canonical([alerts['schema_version'], sid, report['known_at'],
                                                 alerts['stocks'][sid]['config'], check]))
                graph['research_alerts'] = alerts['stocks'][sid]
                for filename, obj in [('alerts.json', alerts), ('research-facts.json', facts),
                                      (manifest['stocks'][0]['path'], graph)]:
                    (path/filename).write_bytes(canonical(obj))
                report['research_facts'].update(sha256=sha(canonical(facts)), size_bytes=len(canonical(facts)))
                report['research_alerts']['sha256'] = sha(canonical(alerts))
                manifest['stocks'][0]['sha256'] = sha(canonical(graph))
                (path/'data/manifest.json').write_bytes(canonical(manifest))
                report['manifest_sha256'] = sha(canonical(manifest))
                (path/'report.json').write_bytes(canonical(report))
                with self.assertRaisesRegex(ValueError, 'market notice'):
                    audit_bundle(self.root/'runs', report['run'])

    def test_each_selected_quote_needs_a_fact_or_its_own_effective_withdrawal(self):
        from local.bundle_audit import audit_bundle
        self.register(self.notice())
        other = CSV.replace(b'1000,Synthetic', b'1001,Synthetic')
        ingest(other, 'twse', ['1001'], DAY, db=self.db, output=self.raw,
               observed_at=T1, acquisition='local_file_unverified')
        withdrawal = self.notice('withdraw', symbol='1001', target=other, replacement=None)
        self.register(withdrawal, replacement=None, symbol='1001')
        bundle = self.audited(T3, ['1000', '1001'])
        path = self.root/'runs'/bundle.report['run']
        notices = [n for n in bundle.facts['market_notices'] if n['notice']['symbol'] == '1000']
        bundle.facts['market_notices'] = bundle.report['quality']['market_notices'] = notices
        body = canonical(bundle.facts)
        (path/'research-facts.json').write_bytes(body)
        bundle.report['research_facts'].update(sha256=sha(body), size_bytes=len(body))
        (path/'report.json').write_bytes(canonical(bundle.report))
        with self.assertRaisesRegex(ValueError, 'coverage'):
            audit_bundle(self.root/'runs', bundle.report['run'])

    def test_rehashed_bundle_cannot_change_a_replacement_ohlc(self):
        from local.bundle_audit import audit_bundle
        from local.research import run
        from local.research_history import canonical
        from test_research_history import payload
        self.register(self.notice())
        (self.root/'input.json').write_bytes(canonical(payload()))
        with patch('local.research.utc_now', return_value=T3), patch('local.research_history.utc_now', return_value=T3):
            report = run(self.root/'input.json', ['1000'], history_db=self.root/'history.db',
                         output_root=self.root/'runs', known_at=T3, alerts=True, prices_db=self.db,
                         price_snapshots=self.raw, trade_date=DAY)
        path = self.root/'runs'/report['run']
        facts = json.loads((path/'research-facts.json').read_bytes())
        next(f for f in facts['facts'] if f['kind'] == 'market_price')['close'] = '10.50'
        body = canonical(facts)
        (path/'research-facts.json').write_bytes(body)
        report['research_facts'].update(sha256=sha(body), size_bytes=len(body))
        (path/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'market notice'):
            audit_bundle(self.root/'runs', report['run'])

    def test_relocated_backup_preserves_withdrawal_and_ordinary_latest_view(self):
        import shutil
        import sqlite3
        from contextlib import closing
        self.register(self.notice('withdraw', replacement=None), replacement=None)
        restored_db, restored_raw = self.root/'restored.db', self.root/'restored-raw'
        with closing(sqlite3.connect(self.db)) as source, closing(sqlite3.connect(restored_db)) as copy:
            source.backup(copy)
            saved, = copy.execute("SELECT raw_sha256 FROM market_prices_latest").fetchone()
            self.assertEqual(saved, sha(CSV))
        shutil.copytree(self.raw, restored_raw)
        self.assertEqual(read_prices(restored_db, 'twse', ['1000'], DAY, T2, restored_raw)[0]['raw_sha256'], sha(CSV))
        self.assertEqual(read_prices(restored_db, 'twse', ['1000'], DAY, T4, restored_raw), [])

    def test_registration_counts_new_row_record_and_replacement_toward_replay(self):
        notice = self.notice()
        evidence_path = self.raw/notice['source_id']/'notices'/(notice['evidence_sha256']+'.bin')
        raw_without_replacement = len(CSV) + (self.root/'notice.txt').stat().st_size
        for policy, limit in [('MAX_HISTORY_ROWS', 1), ('MAX_HISTORY_RECORD_BYTES', 1500),
                              ('MAX_HISTORY_RAW_BYTES', raw_without_replacement)]:
            with self.subTest(policy=policy), patch('local.market_graph.' + policy, limit):
                with self.assertRaisesRegex(ValueError, 'work budget'):
                    self.register(notice)
                self.assertFalse(evidence_path.exists())
                self.assertEqual(self.read(T3)[0]['record']['close'], '11.00')
        self.register(notice)
        self.register(notice, recorded=T4)
        self.assertEqual(self.read(T4)[0]['notice_sha256'], sha(canonical(notice)))

    def test_default_replay_budget_is_checked_before_saving_seventh_large_notice(self):
        from datetime import datetime, timedelta
        from contextlib import redirect_stdout
        import io
        parent, target = None, CSV
        bulletin = b'X' * 19_400_000
        with redirect_stdout(io.StringIO()):
            for index in range(7):
                when = (datetime.fromisoformat(T2) + timedelta(days=index)).isoformat()
                evidence = bytes([65 + index]) + bulletin
                notice = self.notice(published=when, parent=parent, target=target)
                notice['evidence_sha256'] = sha(evidence)
                (self.root/'notice.txt').write_bytes(evidence)
                if index < 6:
                    self.register(notice, recorded=when)
                    parent, target = sha(canonical(notice)), FIXED
                    last = notice
                else:
                    for _ in range(2):
                        with self.assertRaisesRegex(ValueError, 'raw_bytes'):
                            self.register(notice, recorded=when)
                    self.assertFalse((self.raw/notice['source_id']/'notices'/(sha(evidence)+'.bin')).exists())
            (self.root/'notice.txt').write_bytes(b'F' + bulletin)
            self.register(last, recorded=when)
            self.assertEqual(self.read(when)[0]['notice_sha256'], parent)

    def test_original_notice_cannot_be_the_ordinary_csv_even_if_its_hash_matches(self):
        notice = self.notice('withdraw', replacement=None)
        notice['evidence_sha256'] = sha(CSV)
        (self.root/'notice.txt').write_bytes(CSV)
        with self.assertRaisesRegex(ValueError, 'notice evidence'):
            self.register(notice, replacement=None)
        self.assertEqual(self.read(T4)[0]['record']['close'], '11.00')

    def test_scope_evidence_and_same_publication_conflicts_leave_previous_success(self):
        first = self.notice()
        self.register(first)
        parent = sha(canonical(first))
        previous = (self.raw/'latest-twse.json').read_bytes()
        for field, value in [('market', 'tpex'), ('source_id', 'tpex_daily_11371'), ('symbol', '2000'),
                             ('trade_date', '2020-01-01'), ('target_raw_sha256', sha(CSV)),
                             ('target_record_sha256', 'a'*64), ('parent_notice_sha256', None),
                             ('evidence_sha256', 'f'*64), ('evidence_url', 'https://www.tpex.org.tw/notice'),
                             ('published_at', T2)]:
            with self.subTest(field=field):
                notice = self.notice('withdraw', target=FIXED, replacement=None, published=T3, parent=parent)
                notice[field] = value
                with self.assertRaises(ValueError):
                    self.register(notice, recorded=T4, replacement=None)
        new = self.notice(published=T4, parent=parent, target=FIXED, replacement=CSV)
        with self.assertRaisesRegex(ValueError, 'replacement checksum'):
            self.register(new, recorded=T5, replacement=FIXED)
        self.assertEqual(self.read(T5)[0]['raw_sha256'], sha(FIXED))
        self.assertEqual((self.raw/'latest-twse.json').read_bytes(), previous)
        late = CSV.replace(b'1000,Synthetic', b'1001,Synthetic')
        ingest(late, 'twse', ['1001'], DAY, db=self.db, output=self.raw,
               observed_at=T5, acquisition='local_file_unverified')
        self.assertEqual(self.read(T5)[0]['raw_sha256'], sha(FIXED))

    def test_standalone_alert_history_uses_previous_eligible_dates_after_withdrawal(self):
        from local.alert_inputs import load_price_history
        for day in ('2019-12-31', '2020-01-01', '2020-01-03'):
            row = CSV.replace(b'20200102', day.replace('-', '').encode())
            ingest(row, 'twse', ['1000'], day, db=self.db, output=self.raw,
                   observed_at=T2, acquisition='local_file_unverified')
        self.register(self.notice('withdraw', replacement=None), replacement=None)
        history = load_price_history(self.db, 'twse', ['1000'], '2020-01-03', T4,
                                     self.raw, {'volume_window': 2})
        self.assertEqual([row['record']['trade_date'] for row in history['TW:1000']],
                         ['2019-12-31', '2020-01-01', '2020-01-03'])

    def test_corrected_report_cannot_identify_the_original_as_the_selected_quote(self):
        from local.bundle_audit import audit_bundle
        from local.research import run
        from test_research_history import payload
        self.register(self.notice())
        (self.root/'input.json').write_bytes(canonical(payload()))
        with patch('local.research.utc_now', return_value=T3), patch('local.research_history.utc_now', return_value=T3):
            report = run(self.root/'input.json', ['1000'], history_db=self.root/'history.db',
                         output_root=self.root/'runs', known_at=T3, alerts=True, prices_db=self.db,
                         price_snapshots=self.raw, trade_date=DAY)
        report['market_observations'][0]['raw_sha256'] = sha(CSV)
        path = self.root/'runs'/report['run']
        (path/'report.json').write_bytes(canonical(report))
        with self.assertRaisesRegex(ValueError, 'market notice'):
            audit_bundle(self.root/'runs', report['run'])

    def test_tpex_uses_its_own_columns_origin_and_key(self):
        from local.market_prices import FEEDS
        from contextlib import redirect_stdout
        import io
        feed = 'tpex'
        row = CSV.splitlines(keepends=True)[1]
        original = (','.join(FEEDS[feed]['columns'])+'\n').encode()+row
        fixed = original.replace(b'11.00,1000', b'11.50,1000')
        ingest(original, feed, ['1000'], DAY, db=self.db, output=self.raw,
               observed_at=T1, acquisition='local_file_unverified')
        notice = self.notice()
        notice.update(source_id='tpex_daily_11371', market=feed, evidence_url='https://www.tpex.org.tw/notice/example',
                      target_raw_sha256=sha(original), replacement_raw_sha256=sha(fixed),
                      target_record_sha256=sha(canonical(normalize(original, feed, ['1000'], DAY, T1)['records'][0])))
        manifest = self.root/'tpex.json'
        manifest.write_bytes(canonical(notice))
        raw = self.root/'tpex.csv'
        raw.write_bytes(fixed)
        with patch('local.market_notices.utc_now', return_value=T3), redirect_stdout(io.StringIO()):
            main(['--market', feed, '--symbols', '1000', '--expected-date', DAY, '--notice', str(manifest),
                  '--notice-evidence', str(self.root/'notice.txt'), '--input', str(raw),
                  '--db', str(self.db), '--output', str(self.raw)])
        item = read_prices(self.db, feed, ['1000'], DAY, T3, self.raw)[0]
        self.assertEqual((item['source']['source_id'], item['record']['close']), ('tpex_daily_11371', '11.50'))
        self.assertEqual(self.read(T3)[0]['record']['close'], '11.00')
        (self.raw/'tpex_daily_11371'/'notices'/(notice['evidence_sha256']+'.bin')).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'evidence checksum'):
            read_prices(self.db, feed, ['1000'], DAY, T3, self.raw)
        self.assertEqual(read_prices(self.db, feed, ['1000'], DAY, T1, self.raw)[0]['record']['close'], '11.00')
