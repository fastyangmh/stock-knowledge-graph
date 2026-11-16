"""Independent, deterministic reminder rules on synthetic as-known observations."""
import calendar
import copy
import hashlib
import unittest
from datetime import date, timedelta

from local.alerts import DEFAULTS, CAVEATS, evaluate, policy, validate, number

SID = 'TW:1000'
CUTOFF = '2020-08-15T20:00:00+08:00'
TARGET = '2020-08-15'
SOURCE = {'source_id':'fixture', 'dataset_url':'https://example.org/price', 'market':'TWSE'}


def prices(n=21):
    start = date.fromisoformat(TARGET)-timedelta(days=n-1)
    return [{'record':{'symbol':'1000', 'market':'TWSE', 'trade_date':(start+timedelta(days=i)).isoformat(),
                      'close':'105' if i == n-1 else '100', 'volume_shares':2000 if i == n-1 else 1000,
                      'price_unit':'source_reported','price_basis':'source_unadjusted'},
             'source':copy.deepcopy(SOURCE), 'observed_at':(start+timedelta(days=i)).isoformat()+'T18:00:00+08:00',
             'raw_snapshot_verified':True, 'raw_sha256':str(i%10)*64, 'acquisition':'local_file_unverified'} for i in range(n)]


def payload():
    metrics = []
    for month, yoy in ((4,0),(5,10),(6,20),(7,30)):
        day = f'2020-{month:02}-{calendar.monthrange(2020,month)[1]}'
        for kind,value in (('monthly_revenue',1000),('monthly_revenue_yoy_pct',yoy),('monthly_revenue_mom_pct',20)):
            metrics.append({'stock_id':SID,'metric':kind,'period_end':day,'period_type':'month','value':value,
                'unit':'source_reported' if kind=='monthly_revenue' else 'percent','source_id':'fixture',
                'available_at':'2020-08-01T00:00:00Z','registered_at':'2020-08-01T00:00:00Z',
                'input_snapshot_sha256':'a'*64})
    return {'stocks':[{'stock_id':SID,'ticker':'1000','name':'Synthetic','market':'TW'}],
        'sources':[{'source_id':'fixture','provider':'Synthetic','url':'https://example.org/revenue'}],
        'financial_metrics':metrics, 'metadata':{'observed_at':'2020-08-01T00:00:00Z'}}


def compute(data=None, history=None, **kwargs):
    return evaluate(payload() if data is None else data, {SID:prices() if history is None else history},
                    {SID}, CUTOFF, trade_date=TARGET, **kwargs)[SID]


def checks(report):
    return {c['rule_id']:c for group in report['categories'].values() for c in group}


class AlertRuleTests(unittest.TestCase):
    def test_all_thresholds_inclusive_separate_categories(self):
        result=compute();items=checks(result)
        self.assertEqual(set(result['categories']),{'price_volume','monthly_revenue'})
        self.assertTrue(all(c['status']=='triggered' for c in items.values()))
        self.assertEqual(items['price_change']['value'],'5.000000')
        self.assertEqual(items['volume_ratio']['value'],'2.000000')
        self.assertEqual(items['revenue_yoy_change']['value'],'10.000000')
        self.assertNotIn('score',result);self.assertNotIn('action',result)
    def test_volume_baseline_excludes_target(self):
        values=prices();values[-1]['record']['volume_shares']=1000000
        c=checks(compute(history=values))['volume_ratio']
        self.assertEqual(c['baseline']['mean_volume_shares'],'1000.000000')
        self.assertEqual(c['value'],'1000.000000')
        self.assertNotIn(TARGET,c['baseline']['dates'])
        self.assertEqual(len(c['evidence']),21)
    def test_price_below_threshold_not_triggered(self):
        values=prices();values[-1]['record']['close']='104.9999'
        self.assertEqual(checks(compute(history=values))['price_change']['status'],'not_triggered')
    def test_negative_move_triggers_without_buy_sell(self):
        values=prices();values[-1]['record']['close']='95'
        c=checks(compute(history=values))['price_change']
        self.assertEqual(c['status'],'triggered');self.assertEqual(c['value'],'-5.000000')
    def test_zero_volume_target_is_valid_and_not_alert(self):
        values=prices();values[-1]['record']['volume_shares']=0
        self.assertEqual(checks(compute(history=values))['volume_ratio']['status'],'not_triggered')
    def test_zero_baseline_no_infinite_ratio(self):
        values=prices()
        for row in values[:-1]:row['record']['volume_shares']=0
        c=checks(compute(history=values))['volume_ratio']
        self.assertEqual(c['status'],'not_comparable');self.assertIsNone(c['value'])
    def test_price_missing_not_replaced_by_zero_or_earlier_quote(self):
        for value in (None, '0', '-1'):
            with self.subTest(value=value):
                values=prices();values[-2]['record']['close']=value
                self.assertEqual(checks(compute(history=values))['price_change']['status'],'not_comparable')
    def test_only_one_quote_still_shows_insufficient(self):
        result=checks(compute(history=prices(1)))
        self.assertEqual(result['price_change']['status'],'insufficient_data')
        self.assertEqual(result['volume_ratio']['status'],'insufficient_data')
    def test_no_price_input_does_not_block_revenue(self):
        result=evaluate(payload(),{}, {SID},CUTOFF)[SID]
        self.assertTrue(all(c['status']=='insufficient_data' for c in result['categories']['price_volume']))
        self.assertTrue(any(c['status']=='triggered' for c in result['categories']['monthly_revenue']))
    def test_missing_target_does_not_relabel_yesterday(self):
        result=checks(compute(history=prices()[:-1]))
        self.assertEqual(result['price_change']['reason'],'target_price_missing_at_cutoff')
    def test_gap_limit_and_mixed_source_rejected(self):
        for edit in ('gap','source','raw','basis'):
            with self.subTest(edit=edit):
                rows=prices()
                if edit=='gap':rows[-2]['record']['trade_date']='2020-06-01'
                if edit=='source':rows[-1]['source']['source_id']='other'
                if edit=='raw':rows[-1]['raw_snapshot_verified']=False
                if edit=='basis':rows[-1]['record']['price_basis']='adjusted'
                c=checks(compute(history=rows))['volume_ratio']
                self.assertEqual(c['status'],'not_comparable')
    def test_future_price_not_used(self):
        rows=prices();rows[-1]['observed_at']='2020-08-16T00:00:00+08:00'
        self.assertEqual(checks(compute(history=rows))['price_change']['status'],'insufficient_data')
    def test_duplicate_days_and_wrong_stock_are_rejected(self):
        rows=prices();rows.append(copy.deepcopy(rows[0]))
        with self.assertRaises(ValueError):compute(history=rows)
        rows=prices();rows[0]['record']['symbol']='1001'
        with self.assertRaises(ValueError):compute(history=rows)
    def test_invalid_numeric_inputs_rejected(self):
        for value in (True,'NaN','Infinity','',[],1e90):
            with self.subTest(value=value),self.assertRaises(ValueError):number(value)
        rows=prices();rows[-1]['record']['volume_shares']=True
        with self.assertRaises(ValueError):compute(history=rows)
    def test_future_target_rejected(self):
        with self.assertRaises(ValueError):evaluate(payload(),{}, {SID},CUTOFF,trade_date='2020-08-16')
    def test_revenue_no_amount_recalculation_when_percent_absent(self):
        data=payload();data['financial_metrics']=[r for r in data['financial_metrics'] if r['metric']=='monthly_revenue']
        self.assertTrue(all(c['status']=='insufficient_data' for c in compute(data=data)['categories']['monthly_revenue']))
    def test_revenue_latest_missing_percent_does_not_fall_back(self):
        data=payload();data['financial_metrics']=[r for r in data['financial_metrics'] if not
            (r['period_end']=='2020-07-31' and r['metric']=='monthly_revenue_yoy_pct')]
        c=checks(compute(data=data))['revenue_yoy']
        self.assertEqual(c['target_period'],'2020-07-31');self.assertEqual(c['status'],'insufficient_data')
    def test_revenue_percentage_unit_and_source_mismatch(self):
        for edit in ('unit','source'):
            data=payload()
            row=next(r for r in data['financial_metrics'] if r['metric']=='monthly_revenue_yoy_pct' and r['period_end']=='2020-06-30')
            row['unit' if edit=='unit' else 'source_id']='other'
            self.assertEqual(checks(compute(data=data))['revenue_yoy_change']['status'],'not_comparable')
    def test_consecutive_months_required_for_trend(self):
        data=payload();data['financial_metrics']=[r for r in data['financial_metrics'] if r['period_end']!='2020-05-31']
        self.assertEqual(checks(compute(data=data))['revenue_yoy_trend']['status'],'insufficient_data')
    def test_trend_may_be_negative_yoy_but_improving(self):
        data=payload()
        for r in data['financial_metrics']:
            if r['metric']=='monthly_revenue_yoy_pct':r['value']-=100
        self.assertEqual(checks(compute(data=data))['revenue_yoy_trend']['direction'],'increasing')
    def test_declining_and_flat_trends(self):
        data=payload()
        for r in data['financial_metrics']:
            if r['metric']=='monthly_revenue_yoy_pct':r['value']=-r['value']
        self.assertEqual(checks(compute(data=data))['revenue_yoy_trend']['direction'],'decreasing')
        for r in data['financial_metrics']:
            if r['metric']=='monthly_revenue_yoy_pct':r['value']=0
        self.assertEqual(checks(compute(data=data))['revenue_yoy_trend']['status'],'not_triggered')
    def test_late_registered_or_future_available_revenue_excluded(self):
        for field in ('registered_at','available_at'):
            data=payload()
            for row in data['financial_metrics']:row[field]='2021-01-01T00:00:00Z'
            self.assertTrue(all(c['status']=='insufficient_data' for c in compute(data=data)['categories']['monthly_revenue']))
    def test_ambiguous_metric_and_non_month_end_rejected(self):
        data=payload();data['financial_metrics'].append(copy.deepcopy(data['financial_metrics'][0]))
        with self.assertRaises(ValueError):compute(data=data)
        data=payload();data['financial_metrics'][0]['period_end']='2020-07-30'
        with self.assertRaises(ValueError):compute(data=data)
    def test_year_boundary_month_sequence(self):
        data=payload()
        mapping={'2020-04-30':'2019-11-30','2020-05-31':'2019-12-31','2020-06-30':'2020-01-31','2020-07-31':'2020-02-29'}
        for r in data['financial_metrics']:r['period_end']=mapping[r['period_end']]
        self.assertEqual(checks(compute(data=data))['revenue_yoy_trend']['status'],'triggered')
    def test_configuration_validated_not_silently_ignored(self):
        for config in ({'unknown':1},{'volume_window':True},{'volume_window':0},{'revenue_yoy_pct':float('nan')},{'volume_ratio':0}):
            with self.subTest(config=config),self.assertRaises(ValueError):policy(config)
        result=compute(config={'price_change_pct':6,'volume_ratio':3})
        self.assertEqual(checks(result)['price_change']['status'],'not_triggered')
        self.assertEqual(checks(result)['volume_ratio']['status'],'not_triggered')
    def test_deterministic_and_inputs_not_mutated(self):
        data,rows=payload(),prices();before=copy.deepcopy((data,rows))
        one=compute(data,rows);two=compute(data,rows)
        self.assertEqual(one,two);self.assertEqual((data,rows),before)
        self.assertNotEqual(checks(one)['price_change']['id'],checks(compute(config={'price_change_pct':4}))['price_change']['id'])
    def test_hash_and_future_evidence_tamper_fail_validation(self):
        for edit in ('value','future','missing','stock'):
            result=compute()
            if edit=='value':result['categories']['price_volume'][0]['value']='99'
            if edit=='future':result['categories']['price_volume'][0]['evidence'][0]['observed_at']='2099-01-01T00:00:00Z'
            if edit=='missing':result['categories']['monthly_revenue'].pop()
            if edit=='stock':result['stock_id']='TW:9999'
            with self.subTest(edit=edit),self.assertRaises(ValueError):validate(result,SID)
