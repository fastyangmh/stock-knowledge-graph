"""Pure math/time tests: synthetic saved observations, no market or trading claims."""
import copy
import unittest
from unittest.mock import patch

from local.event_study import analyze, policy, summarize, DEFAULTS
from local.event_outcomes import month_end_offset
from local.alerts import evaluate
from test_alerts import payload, prices, SID, CUTOFF, TARGET
from event_fixtures import bundle, complete_bundle, revenue, outcome, event

ASOF='2020-12-31T23:59:59+08:00'
CONFIG={'quote_horizons':[1,2],'revenue_horizons':[1,3]}


def defined_bundle(n, category, key, value, *, complete=True):
    data, history = payload(), prices()
    rows = ([item['record'] for item in history] if category == 'price_volume'
            else data['financial_metrics'])
    for row in rows:
        row[key] = value
    result = (complete_bundle if complete else bundle)(
        n, data=data, completed=f'2020-08-{15+n:02}T20:01:00+08:00')
    saved = result.facts['facts'] if complete else result.graphs[SID]['nodes']
    kind = 'market_price' if category == 'price_volume' else 'financial_metric'
    for row in saved:
        if row.get('kind',row.get('type')) == kind:
            row[key] = value
    result.alerts = {'stocks':evaluate(data, {SID:history}, {SID}, CUTOFF, trade_date=TARGET)}
    return result


class EventDefinitionTests(unittest.TestCase):
    def test_changed_definitions_preserve_events_and_separate_summary_denominators(self):
        cases = [('price_volume', key, first, second, 4) for key,first,second in (
            ('market','TWSE','TPEX'), ('price_unit','source_reported','TWD'),
            ('price_basis','source_unadjusted','adjusted'), ('price_currency','TWD','USD'),
            ('volume_unit','shares','lots'), ('turnover_unit','TWD','USD'),
            ('turnover_currency','TWD','USD'), ('trades_unit','trades','other'),
            ('trading_scope','regular_only','regular_oddlot_afterhours'),
            ('normalization_version','market-v1','market-v2'))]
        cases += [('monthly_revenue',key,first,second,8) for key,first,second in (
            ('normalization_version','revenue-v1','revenue-v2'), ('currency','TWD','USD'),
            ('statement_scope','consolidated','separate'), ('report_basis','single_period','cumulative'),
            ('consolidation','consolidated','separate'), ('value_basis','single_period','cumulative'))]
        for category,key,first,second,total in cases:
            with self.subTest(category=category, key=key):
                a = defined_bundle(1,category,key,first)
                b = defined_bundle(2,category,key,second)
                result = analyze([a,b],ASOF,CONFIG)['categories'][category]
                self.assertEqual(len(result['events']),total)
                self.assertEqual(len({e['definition_id'] for e in result['events']}),total)
                self.assertTrue(all(e['repeated_captures']==0 for e in result['events']))
                self.assertTrue(all(s['n_total']==1 for s in result['summaries']))

    def test_changed_definition_is_not_excluded_as_an_earlier_legacy_trigger(self):
        old = defined_bundle(1,'monthly_revenue','statement_scope','separate',complete=False)
        new = defined_bundle(2,'monthly_revenue','statement_scope','consolidated')
        result = analyze([old,new],ASOF,CONFIG,cohort='unpruned_facts')
        self.assertEqual(len(result['categories']['monthly_revenue']['events']),4)
        self.assertEqual({e['rule_id'] for e in result['excluded_events']},{'price_change','volume_ratio'})

    def test_new_provenance_with_same_definition_remains_a_repeat(self):
        first = defined_bundle(1,'price_volume','trading_scope','regular_only')
        data, history = payload(), prices()
        for item in history:
            item['record']['trading_scope'] = 'regular_only'
            item['raw_sha256'] = 'f'*64
            item['observed_at'] = '2020-08-15T19:00:00+08:00'
        for row in data['financial_metrics']:
            row['input_snapshot_sha256'] = 'f'*64
        second = complete_bundle(2,completed='2020-08-18T20:01:00+08:00')
        second.alerts = {'stocks':evaluate(data,{SID:history},{SID},CUTOFF,trade_date=TARGET)}
        result = analyze([first,second],ASOF,CONFIG)
        self.assertEqual(result['counts']['events'],6)
        self.assertEqual(result['counts']['duplicate_period_events_suppressed'],6)

    def test_legacy_event_identity_hashes_remain_unchanged_with_absent_definitions(self):
        # Captured through public analyze at pre-fix 0b21300, not recomputed expectations.
        expected = {
            'price_change':('7abcd4c5982281fd8b3971db734d58ebcaa395389b2e81caf12ea01f027788c8','24534c862cec88ffb3abf1f8ed8d55a430ef07e66a3aa2bf0f0bc753946df830'),
            'volume_ratio':('47dacaae87e656ec626994c4a0fa736ac3ce6baeaee41eb20edbea9db0f5ab0a','441fa9627228b67105f119e8f9464b84e54e483e5ccfd404a9192302cdd0718b'),
            'revenue_mom':('c9a7462a604c411a6877df92d92601cee5961e62404d7e2f1b8f645a239004dd','4476051f5c0f12df5fe32e6f2bb4936b3fef5a6c81b63f43561d7ab47bd83e27'),
            'revenue_yoy':('c43b0516bce57fba864e4f286527feed83035e87eb3004d5b491d0a69088e638','f7dc118b4bc35cd3ebf249b16fcd8497b7c22c9e4ef43241bc220ee62336a727'),
            'revenue_yoy_change':('2e309c7c2b3055e08c7827fdb8336fa9be0d46b520770a92f5184f53ef3af85c','5c05f3a59714c2b7c0abc2d9905058af8dfbcebd1e586791878b2e631b78f913'),
            'revenue_yoy_trend':('2836c75fbe5dcd5966205c5b59e7644530ae89de571479ddaec2f4e6368bbf5d','e44c59c9088b1bc7a97b764d9669b4045bf0ea744fe4fe7e9cb4fc1e3a22e2a4'),
        }
        for legacy in (bundle(alerts=True),defined_bundle(1,'monthly_revenue','currency',None,complete=False)):
            with self.subTest(run=legacy.report['run']):
                result = analyze([legacy],ASOF)
                self.assertEqual({e['rule_id']:(e['event_id'],e['definition_id'])
                    for category in result['categories'].values() for e in category['events']},expected)

class EventStudyTests(unittest.TestCase):
    def setUp(self):
        self.first=bundle(alerts=True)
        self.next=bundle(2,'2020-08-16',close='115.5',volume=1000)
        self.third=bundle(3,'2020-08-17',close='94.5',volume=0)
    def study(self,items=None,**kw):
        return analyze(items if items is not None else [self.first,self.next,self.third],ASOF,kw.pop('config',CONFIG),**kw)
    def test_default_horizons_separate_and_not_mutated(self):
        p=policy();p['quote_horizons'].append(100)
        self.assertEqual(policy(),DEFAULTS)
        self.assertEqual(policy()['quote_horizons'],[1,5,20])
    def test_invalid_configuration(self):
        for config in ({'win_rate':True},{'quote_horizons':[]},{'quote_horizons':[2,1]},
                       {'quote_horizons':[1,1]},{'quote_horizons':[True]}, {'quote_horizons':[253]},
                       {'revenue_horizons':[25]},{'revenue_horizons':'1'},{'max_quote_gap_days':0},
                       {'max_quote_gap_days':True},{'quote_horizons':[1,2,3,4,5,6,7]}):
            with self.subTest(config=config),self.assertRaises(ValueError):policy(config)
    def test_exact_post_event_price_and_volume(self):
        r=self.study()
        self.assertEqual(outcome(r)['value'],'10.000000')
        self.assertEqual(outcome(r,metric='close_change_pct',horizon=2)['value'],'-10.000000')
        self.assertEqual(outcome(r,metric='volume_ratio')['value'],'0.500000')
        self.assertEqual(outcome(r,metric='volume_ratio',horizon=2)['value'],'0.000000')
        self.assertFalse(r['combined_score']);self.assertFalse(r['trade_assumptions'])
        self.assertEqual(r['counts']['events'],6)
        self.assertEqual(set(r['categories']),{'price_volume','monthly_revenue'})
    def test_no_first_crossing_or_trade_assumption(self):
        r=self.study();self.assertIn('not_crossing_episodes',r['event_policy'])
        self.assertEqual(outcome(r)['horizon_unit'],'quote_observations')
    def test_reruns_suppress_same_period_even_new_alert_ids(self):
        repeated=bundle(9,alerts=True,completed='2020-08-16T12:00:00+08:00')
        r=self.study([self.first,repeated,self.next])
        self.assertEqual(r['counts']['events'],6)
        self.assertEqual(r['counts']['duplicate_period_events_suppressed'],6)
        self.assertTrue(all(e['repeated_captures']==1 for g in r['categories'].values() for e in g['events']))
    def test_original_input_not_mutated_and_deterministic(self):
        before=copy.deepcopy(self.first)
        a=self.study();b=self.study([self.third,self.next,self.first])
        self.assertEqual(a,b);self.assertEqual(self.first,before)
    def test_future_run_excluded_even_with_old_knowledge(self):
        self.next.report['completed_at']='2099-01-01T00:00:00Z'
        r=self.study([self.first,self.next])
        self.assertEqual(r['counts']['runs_after_cutoff'],1)
        self.assertEqual(outcome(r)['status'],'insufficient_data')
    def test_future_analysis_refused(self):
        with self.assertRaises(ValueError):analyze([self.first],'2099-01-01T00:00:00Z')
    def test_naive_cutoff_refused(self):
        with self.assertRaises(ValueError):analyze([self.first],'2020-01-01T12:00:00')
    def test_event_time_is_actual_completion_not_historical_cutoff(self):
        self.first.report['completed_at']='2020-08-20T21:00:00+08:00'
        r=self.study()
        self.assertEqual(event(r)['event_at'],'2020-08-20T13:00:00+00:00')
        self.assertEqual(outcome(r)['status'],'insufficient_data')
    def test_same_day_quote_not_future_endpoint(self):
        same=bundle(4,'2020-08-15',close='200',completed='2020-08-15T23:00:00+08:00')
        r=self.study([self.first,same,self.next])
        self.assertEqual(outcome(r)['value'],'10.000000')
        self.assertEqual(outcome(r)['target_period'],'2020-08-16')
    def test_first_saved_revision_not_latest_revision(self):
        revised=bundle(5,'2020-08-16',close='500',completed='2020-08-18T22:00:00+08:00')
        r=self.study([self.first,self.next,revised])
        self.assertEqual(outcome(r)['value'],'10.000000')
        self.assertEqual(outcome(r)['followup']['run'],self.next.report['run'])
    def test_baseline_is_never_revised_from_later_bundle(self):
        revised=bundle(5,'2020-08-15',close='500',completed='2020-08-18T22:00:00+08:00')
        r=self.study([self.first,revised,self.next])
        self.assertEqual(outcome(r)['baseline']['close'],'105')
    def test_missing_close_not_skipped_to_next_good_quote(self):
        self.next.graphs[SID]['nodes'][-1]['close']=None
        r=self.study()
        self.assertEqual(outcome(r)['status'],'not_comparable')
        self.assertEqual(outcome(r)['target_period'],'2020-08-16')
        self.assertEqual(outcome(r,horizon=2)['status'],'observed')
    def test_zero_baseline_volume_not_infinite(self):
        self.first.graphs[SID]['nodes'][-1]['volume_shares']=0
        self.assertEqual(outcome(self.study(),metric='volume_ratio')['status'],'not_comparable')
    def test_nonpositive_price_not_total_return(self):
        self.next.graphs[SID]['nodes'][-1]['close']='0'
        self.assertEqual(outcome(self.study())['status'],'not_comparable')
    def test_source_and_basis_changes_not_silently_skipped(self):
        for key,value in [('source_id','other'),('price_basis','adjusted'),('price_unit','TWD'),('market','TPEX')]:
            with self.subTest(key=key):
                b=copy.deepcopy(self.next);b.graphs[SID]['nodes'][-1][key]=value
                self.assertEqual(outcome(self.study([self.first,b,self.third]),horizon=2)['reason'],'quote_source_or_basis_changed')
    def test_unverified_quote_not_comparable(self):
        self.next.graphs[SID]['nodes'][-1]['raw_snapshot_verified']=False
        self.assertEqual(outcome(self.study())['status'],'not_comparable')
    def test_large_gap_not_comparable(self):
        b=bundle(6,'2020-09-20',close='110')
        self.assertEqual(outcome(self.study([self.first,b]))['reason'],'observed_quote_gap_exceeds_policy')
    def test_stale_baseline(self):
        self.first.report['completed_at']='2020-09-01T21:00:00+08:00'
        self.assertEqual(outcome(self.study())['reason'],'stale_event_baseline')
    def test_alert_baseline_date_mismatch(self):
        node=self.first.graphs[SID]['nodes'][-1];node['trade_date']='2020-08-14'
        self.assertEqual(outcome(self.study())['reason'],'alert_and_baseline_period_differ')
    def test_related_stock_numeric_nodes_not_counted(self):
        row=copy.deepcopy(self.first.graphs[SID]['nodes'][-1]);row['symbol']='9999';row['id']='other';row['close']='999'
        self.first.graphs[SID]['nodes'].append(row)
        self.assertEqual(outcome(self.study())['baseline']['close'],'105')
    def test_duplicate_numeric_period_rejected(self):
        self.first.graphs[SID]['nodes'].append(copy.deepcopy(self.first.graphs[SID]['nodes'][-1]))
        with self.assertRaisesRegex(ValueError,'ambiguous'):self.study()
    def test_future_fact_availability_rejected(self):
        self.next.graphs[SID]['nodes'][-1]['observed_at']='2099-01-01T00:00:00Z'
        with self.assertRaises(ValueError):self.study()
    def test_boolean_volume_and_nonfinite_price_rejected(self):
        for key,value in [('volume_shares',True),('close','NaN')]:
            with self.subTest(key=key):
                b=copy.deepcopy(self.next);b.graphs[SID]['nodes'][-1][key]=value
                with self.assertRaises(ValueError):self.study([self.first,b])
    def test_month_offsets_cross_year_and_leap(self):
        self.assertEqual(month_end_offset('2019-11-30',3),'2020-02-29')
        self.assertEqual(month_end_offset('2020-02-29',12),'2021-02-28')
        with self.assertRaises(ValueError):month_end_offset('2020-02-20',1)
    def test_revenue_yoy_points_not_percent_growth(self):
        b=bundle(6,'2020-09-10',data=revenue())
        row=outcome(self.study([self.first,b]),metric='revenue_yoy_change_pp')
        self.assertEqual(row['value'],'15.000000');self.assertEqual(row['unit'],'percentage_points')
    def test_unknown_amount_scale_not_recalculated(self):
        b=bundle(6,'2020-09-10',data=revenue())
        row=outcome(self.study([self.first,b]),metric='revenue_change_pct')
        self.assertEqual(row['status'],'not_comparable');self.assertIsNone(row['value'])
    def test_explicit_money_unit_currency_allows_description(self):
        for n in self.first.graphs[SID]['nodes']:
            if n.get('metric')=='monthly_revenue':n.update(unit='thousand_TWD',currency='TWD')
        b=bundle(6,'2020-09-10',data=revenue(unit='thousand_TWD',currency='TWD'))
        self.assertEqual(outcome(self.study([self.first,b]),metric='revenue_change_pct')['value'],'20.000000')
    def test_missing_currency_even_known_unit_refused(self):
        for n in self.first.graphs[SID]['nodes']:
            if n.get('metric')=='monthly_revenue':n['unit']='TWD'
        self.assertEqual(outcome(self.study(),metric='revenue_change_pct')['status'],'not_comparable')
    def test_revenue_future_month_pending(self):
        r=analyze([self.first,self.next],'2020-08-17T23:00:00+08:00',CONFIG)
        self.assertEqual(outcome(r,metric='revenue_yoy_change_pp')['status'],'pending')
    def test_missing_month_not_nearest_fill(self):
        b=bundle(6,'2020-10-10',data=revenue('2020-09-30'))
        row=outcome(self.study([self.first,b]),metric='revenue_yoy_change_pp')
        self.assertEqual(row['status'],'insufficient_data');self.assertEqual(row['target_period'],'2020-08-31')
    def test_pre_event_revenue_month_not_post_event(self):
        self.first.report['completed_at']='2020-10-15T20:00:00+08:00'
        r=self.study()
        self.assertEqual(outcome(r,metric='revenue_yoy_change_pp')['reason'],'target_month_not_after_actual_event_capture')
    def test_revenue_source_unit_or_scope_switch(self):
        for key,value in [('source_id','other'),('unit','basis_points'),('consolidation','individual')]:
            with self.subTest(key=key):
                data=revenue()
                for m in data['financial_metrics']:m[key]=value
                b=bundle(6,'2020-09-10',data=data)
                self.assertEqual(outcome(self.study([self.first,b]),metric='revenue_yoy_change_pp')['status'],'not_comparable')
    def test_latest_period_missing_yoy_does_not_fallback(self):
        extra=revenue('2020-08-31')['financial_metrics'][0]
        extra['registered_at']=extra['available_at']='2020-08-15T00:00:00Z'
        # Use a valid later period relative to an older existing baseline instead.
        for n in self.first.graphs[SID]['nodes']:
            if n.get('metric')=='monthly_revenue_yoy_pct' and n['period_end']=='2020-07-31':
                n['metric']='not_selected'
        self.assertEqual(outcome(self.study(),metric='revenue_yoy_change_pp')['reason'],'missing_event_baseline')
    def test_missing_baseline_market_does_not_remove_events(self):
        self.first.graphs[SID]['nodes']=self.first.graphs[SID]['nodes'][:-1]
        r=self.study();self.assertEqual(r['counts']['events'],6)
        self.assertEqual(outcome(r)['status'],'insufficient_data')
    def test_no_alerts_or_no_eligible_runs_explicit_empty(self):
        r=self.study([self.next]);self.assertEqual(r['counts']['events'],0)
        self.assertTrue(all(not g['summaries'] for g in r['categories'].values()))
        r=analyze([self.first],'2019-01-01T00:00:00Z')
        self.assertEqual(r['counts']['included_runs'],0)
    def test_duplicate_bundle_refused(self):
        with self.assertRaisesRegex(ValueError,'duplicate research'):self.study([self.first,self.first])
    def test_trigger_tampering_rejected(self):
        self.first.alerts['stocks'][SID]['categories']['price_volume'][0]['value']='999'
        with self.assertRaisesRegex(ValueError,'hash'):self.study()
    def test_event_and_fact_budgets(self):
        with patch('local.event_study.MAX_EVENTS',1),self.assertRaisesRegex(ValueError,'event budget'):self.study()
        with patch('local.event_study.MAX_FACTS',1),self.assertRaisesRegex(ValueError,'fact budget'):self.study()
    def test_report_size_budget(self):
        with patch('local.event_study.MAX_REPORT_BYTES',1),self.assertRaisesRegex(ValueError,'report budget'):self.study()
    def test_denominators_include_unavailable(self):
        r=self.study([self.first,self.next])
        rows=r['categories']['price_volume']['summaries']
        self.assertTrue(any(s['n_observed']==0 and s['n_unavailable']==1 for s in rows))
        self.assertTrue(all(s['n_total']==sum(s['status_counts'].values()) for s in rows))
        self.assertTrue(all(s['statistics'] is None for s in rows if not s['n_observed']))
    def test_summary_statistics_no_win_rate_or_cross_rule_pooling(self):
        e=event(self.study());b=copy.deepcopy(e);b['event_id']='new';b['outcomes'][0]['value']='20'
        g=summarize([e,b]);row=next(s for s in g if s['metric']=='close_change_pct' and s['horizon']==1)
        self.assertEqual(row['n_total'],2);self.assertEqual(row['statistics']['mean'],'15.000000')
        self.assertEqual(row['statistics']['median'],'15.000000')
        self.assertNotIn('win_rate',row)
    def test_negative_direction_does_not_pool_with_positive(self):
        e=event(self.study());b=copy.deepcopy(e);b['direction']='negative';b['event_id']='negative'
        self.assertEqual(len(summarize([e,b])),2*len(summarize([e])))
    def test_changed_definition_creates_separate_cohort(self):
        e=event(self.study());b=copy.deepcopy(e);b['definition_id']='different';b['event_id']='changed'
        self.assertEqual(len(summarize([e,b])),2*len(summarize([e])))
    def test_same_time_conflicting_future_fact_refused(self):
        b=bundle(4,'2020-08-16',close='999',completed=self.next.report['completed_at'])
        with self.assertRaisesRegex(ValueError,'same-time outcome'):self.study([self.first,self.next,b])

    def test_work_budget_fails_before_measurements(self):
        with patch('local.event_study.MAX_FACT_VISITS',1),self.assertRaisesRegex(ValueError,'work budget'):self.study()
    def test_extreme_ratio_is_not_a_nan_or_overflowed_estimate(self):
        self.first.graphs[SID]['nodes'][-1]['close']='0.000000000000000000000000000001'
        self.next.graphs[SID]['nodes'][-1]['close']='1000000000000000000000000000000000000000000000000000000'
        self.assertEqual(outcome(self.study())['reason'],'numeric_ratio_out_of_bounds')
    def test_negative_yoy_can_improve_without_becoming_positive(self):
        for n in self.first.graphs[SID]['nodes']:
            if n.get('metric')=='monthly_revenue_yoy_pct' and n['period_end']=='2020-07-31':n['value']=-30
        b=bundle(6,'2020-09-10',data=revenue(yoy=-10))
        row=outcome(self.study([self.first,b]),metric='revenue_yoy_change_pp')
        self.assertEqual(row['value'],'20.000000')
        self.assertEqual(row['followup']['value'],-10)


    def test_unknown_currency_text_is_not_a_verified_monetary_definition(self):
        for n in self.first.graphs[SID]['nodes']:
            if n.get('metric') == 'monthly_revenue': n.update(unit='TWD',currency='unknown')
        future = bundle(6,'2020-09-10',data=revenue(unit='TWD',currency='unknown'))
        self.assertEqual(outcome(self.study([self.first,future]),metric='revenue_change_pct')['status'],'not_comparable')


class CompleteFactStudyTests(unittest.TestCase):
    def setUp(self):
        from event_fixtures import complete_bundle
        self.factory=complete_bundle
        self.first=complete_bundle(alerts=True)
        self.next=complete_bundle(2,'2020-08-16',close='115.5')
    def study(self,items=None,**kw):
        return analyze(items or [self.first,self.next],ASOF,CONFIG,**kw)
    def test_first_followup_and_missing_baseline_are_never_backfilled(self):
        revised=self.factory(3,'2020-08-16',close='500',completed='2020-08-18T22:00:00+08:00')
        self.assertEqual(outcome(self.study([self.first,self.next,revised]))['value'],'10.000000')
        self.first.facts['facts']=[f for f in self.first.facts['facts'] if f['kind']!='market_price']
        late=self.factory(4,close='500',completed='2020-08-19T22:00:00+08:00')
        self.assertEqual(outcome(self.study([self.first,self.next,late]))['reason'],'missing_event_baseline')
    def test_complete_scope_source_units_and_normalization_remain_separate(self):
        for key,value in [('normalization_version','synthetic-2'),('price_unit','other'),('source_id','other')]:
            with self.subTest(key=key):
                revised=copy.deepcopy(self.next)
                next(f for f in revised.facts['facts'] if f['kind']=='market_price')[key]=value
                self.assertEqual(outcome(self.study([self.first,revised]))['status'],'not_comparable')
    def test_unknown_registration_is_not_fabricated_and_future_availability_fails(self):
        row=outcome(self.study())['baseline']
        self.assertIsNone(row['recorded_at'])
        self.assertEqual(row['recorded_at_status'],'unknown')
        next(f for f in self.next.facts['facts'] if f['kind']=='market_price')['available_at']='2099-01-01T00:00:00Z'
        with self.assertRaises(ValueError):self.study()
    def test_unknown_contract_does_not_use_graph_fallback(self):
        self.first.facts['schema_version']='unknown'
        with self.assertRaisesRegex(ValueError,'schema'):self.study()
    def test_all_complete_numeric_facts_count_towards_budget(self):
        limit=len(self.first.facts['facts'])+len(self.next.facts['facts'])+1
        self.first.facts['facts'].extend([{'kind':'chip_metric','stock_id':SID}]*20)
        with patch('local.event_study.MAX_FACTS',limit),self.assertRaisesRegex(ValueError,'fact budget'):
            self.study()
    def test_event_work_and_report_budgets_apply_to_complete_contract(self):
        for name,value,error in [('MAX_EVENTS',1,'event budget'),('MAX_FACT_VISITS',1,'work budget'),('MAX_REPORT_BYTES',1,'report budget')]:
            with self.subTest(name=name),patch('local.event_study.'+name,value),self.assertRaisesRegex(ValueError,error):
                self.study()
    def test_empty_complete_scope_and_pending_month_keep_explicit_status(self):
        self.assertEqual(self.study([self.next])['counts']['events'],0)
        result=analyze([self.first],'2020-08-16T23:00:00+08:00',CONFIG)
        self.assertEqual(outcome(result,metric='revenue_yoy_change_pp')['status'],'pending')
        self.assertEqual(result['fact_scope'],'unpruned_facts')
    def test_legacy_retains_original_version_and_explicit_scope(self):
        result=analyze([bundle(alerts=True)],ASOF)
        self.assertEqual(result['schema_version'],'event-study-1.0')
        self.assertEqual(result['fact_scope'],'display_graph_only')
        with self.assertRaisesRegex(ValueError,'unknown event fact cohort'):
            self.study(cohort='all')
