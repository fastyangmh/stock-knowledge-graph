import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from local.bundle_audit import audit_bundle, AuditError
from local.research_compare import compare, main, _rule_diff
from local.alerts import evaluate
from history_fixtures import make_run
from test_alerts import payload, prices, SID, CUTOFF, TARGET


def find(report,rule,stock=SID):
    return next(row for item in report['stocks'] if item['stock_id']==stock
                for values in item['categories'].values() for row in values if row['rule_id']==rule)


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def bundle(self,n,**kw):
        report=make_run(self.root,n,**kw);return audit_bundle(self.root/'runs',report['run'])
    def test_activated_with_same_definition(self):
        result=compare(self.bundle(1,value=10),self.bundle(2,value=40))
        check=find(result,'revenue_yoy');self.assertEqual(check['transition'],'activated');self.assertTrue(check['comparable'])
        self.assertFalse(result['combined_score']);self.assertEqual(set(result['stocks'][0]['categories']),{'price_volume','monthly_revenue'})
    def test_no_longer_triggered_is_not_risk_resolution(self):
        result=compare(self.bundle(1,value=40),self.bundle(2,value=10))
        self.assertEqual(find(result,'revenue_yoy')['transition'],'no_longer_triggered')
    def test_missing_data_is_not_an_all_clear(self):
        result=compare(self.bundle(1),self.bundle(2,missing=True))
        check=find(result,'revenue_yoy');self.assertEqual(check['transition'],'became_unavailable');self.assertFalse(check['comparable'])
    def test_first_evaluable_is_not_new_signal(self):
        result=compare(self.bundle(1,missing=True),self.bundle(2))
        self.assertEqual(find(result,'revenue_yoy')['transition'],'became_evaluable')
    def test_missing_on_both_sides_explicit(self):
        result=compare(self.bundle(1,missing=True),self.bundle(2,missing=True))
        self.assertEqual(find(result,'revenue_yoy')['transition'],'still_unavailable')
    def test_changed_threshold_never_activated(self):
        result=compare(self.bundle(1,config={'revenue_yoy_pct':99}),self.bundle(2))
        self.assertEqual(find(result,'revenue_yoy')['transition'],'definition_changed')
        self.assertFalse(find(result,'revenue_yoy')['comparable'])
    def test_only_relevant_settings_invalidate_rule(self):
        result=compare(self.bundle(1,config={'volume_ratio':99}),self.bundle(2))
        self.assertEqual(find(result,'volume_ratio')['transition'],'definition_changed')
        self.assertEqual(find(result,'revenue_yoy')['transition'],'still_triggered')
    def test_source_change_not_signal(self):
        result=compare(self.bundle(1,source='one'),self.bundle(2,source='two'))
        self.assertEqual(find(result,'revenue_yoy')['reason'],'evidence_source_changed')
    def test_no_prior_alerts_not_false_new_signal(self):
        result=compare(self.bundle(1,alerts=False),self.bundle(2))
        self.assertEqual(find(result,'revenue_yoy')['transition'],'not_computed')
    def test_new_stock_is_coverage_not_new_signal(self):
        result=compare(self.bundle(1),self.bundle(2,symbols=['1000','1001']))
        self.assertEqual(result['selection']['added'],['TW:1001'])
        self.assertEqual(find(result,'price_change','TW:1001')['transition'],'added_coverage')
    def test_removed_stock_not_risk_resolution(self):
        result=compare(self.bundle(1,symbols=['1000','1001']),self.bundle(2))
        self.assertEqual(find(result,'price_change','TW:1001')['transition'],'removed_coverage')
    def test_backward_time_rejected(self):
        a,b=self.bundle(1),self.bundle(2)
        with self.assertRaisesRegex(AuditError,'cutoff'):compare(b,a)
    def test_comparison_deterministic_and_inputs_unchanged(self):
        a,b=self.bundle(1),self.bundle(2)
        before=copy.deepcopy(a.report);first=compare(a,b);second=compare(a,b)
        self.assertEqual(first,second);self.assertEqual(a.report,before)
    def test_graph_changes_describe_display_only(self):
        result=compare(self.bundle(1,value=10),self.bundle(2,value=40))
        node=result['stocks'][0]['graph']['nodes'];self.assertGreater(node['counts']['changed'],0)
        self.assertIn('display',result['scope'])
    def test_legacy_configuration_not_assumed_same(self):
        a,b=self.bundle(1),self.bundle(2);a.report.pop('configuration')
        self.assertEqual(compare(a,b)['graph_configuration'],'unknown')
    def test_same_bundle_not_changed_only_by_timestamp(self):
        a=self.bundle(1);result=compare(a,a)
        self.assertEqual(result['stocks'][0]['graph']['nodes']['counts']['changed'],0)
        self.assertEqual(find(result,'revenue_yoy')['changed_fields'],[])
    def test_cli_real_audit_and_json(self):
        a,b=self.bundle(1),self.bundle(2)
        with redirect_stdout(io.StringIO()) as out:main(['--root',str(self.root/'runs'),'--before',a.report['run'],'--after',b.report['run']])
        self.assertEqual(json.loads(out.getvalue())['after']['run'],b.report['run'])
    def test_invalid_detail_limit(self):
        a=self.bundle(1)
        for value in (0,-1,True,501):
            with self.subTest(value=value),self.assertRaises(AuditError):compare(a,a,detail_limit=value)
    def test_price_volume_transition_is_independent_of_revenue(self):
        first=prices();first[-1]['record']['close']='101';first[-1]['record']['volume_shares']=1500
        r1=evaluate(payload(),{SID:first},{SID},CUTOFF,trade_date=TARGET)[SID]
        r2=evaluate(payload(),{SID:prices()},{SID},CUTOFF,trade_date=TARGET)[SID]
        for a,b in zip(r1['categories']['price_volume'],r2['categories']['price_volume']):
            self.assertEqual(_rule_diff(a['rule_id'],r1,a,r2,b)['transition'],'activated')

    def test_legacy_price_evidence_does_not_assume_same_basis(self):
        a=evaluate(payload(),{SID:prices()},{SID},CUTOFF,trade_date=TARGET)[SID]
        b=copy.deepcopy(a)
        row=a['categories']['price_volume'][0]
        for evidence in row['evidence']:evidence.pop('price_basis')
        diff=_rule_diff('price_change',a,row,b,b['categories']['price_volume'][0])
        self.assertEqual(diff['transition'],'definition_unknown');self.assertFalse(diff['comparable'])

    def test_changed_price_basis_is_not_an_alert_transition(self):
        a=evaluate(payload(),{SID:prices()},{SID},CUTOFF,trade_date=TARGET)[SID]
        b=copy.deepcopy(a)
        for row in b['categories']['price_volume'][0]['evidence']:row['price_basis']='another_basis'
        diff=_rule_diff('price_change',a,a['categories']['price_volume'][0],b,b['categories']['price_volume'][0])
        self.assertEqual(diff['reason'],'price_basis_or_scale_changed');self.assertFalse(diff['comparable'])
