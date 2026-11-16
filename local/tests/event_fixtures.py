"""Synthetic in-memory bundles for math tests; real persisted bundles tested separately."""
import copy
import hashlib
from local.alerts import evaluate
from local.bundle_audit import Bundle
from local.research_history import canonical
from test_alerts import payload, prices, SID, CUTOFF, TARGET


def bundle(n=1, day=TARGET, *, alerts=False, close='105', volume=2000, data=None,
           completed=None, known=None, market=True):
    data=copy.deepcopy(data or payload())
    known=known or day+'T20:00:00+08:00'
    completed=completed or day+'T20:01:00+08:00'
    name=f'{n:032x}'
    nodes=[{'id':'stock:'+SID,'type':'stock','label':'Synthetic'}]
    for i,metric in enumerate(data.get('financial_metrics',[])):
        nodes.append({'id':f'metric:{i}','type':'financial_metric','source_url':'https://example.org/revenue',**metric})
    if market:
        nodes.append({'id':'market:fixture:'+day,'type':'market_price','symbol':'1000',
            'source_id':'fixture','source_url':'https://example.org/price','market':'TWSE',
            'close':close,'volume_shares':volume,'price_unit':'source_reported','price_basis':'source_unadjusted',
            'trade_date':day,'observed_at':day+'T18:00:00+08:00','raw_snapshot_verified':True,
            'raw_sha256':'a'*64,'acquisition':'local_file_unverified'})
    graph={'stock_id':SID,'nodes':nodes,'edges':[]}
    report={'run':name,'known_at':known,'completed_at':completed}
    alert=None
    if alerts:
        alert={'stocks':evaluate(data,{SID:prices()}, {SID}, known,trade_date=TARGET)}
    return Bundle(report,hashlib.sha256(canonical(report)).hexdigest(),{}, {SID:graph},{},alert,0,False)


def revenue(month='2020-08-31',value=1200,yoy=45,unit='source_reported',currency=None):
    data=payload()
    data['financial_metrics']=[]
    for metric,v,u in [('monthly_revenue',value,unit),('monthly_revenue_yoy_pct',yoy,'percent')]:
        row={'stock_id':SID,'metric':metric,'value':v,'unit':u,'source_id':'fixture',
             'period_end':month,'period_type':'month','available_at':'2020-09-01T00:00:00Z',
             'registered_at':'2020-09-01T00:00:00Z','input_snapshot_sha256':'b'*64}
        if currency and metric=='monthly_revenue':row['currency']=currency
        data['financial_metrics'].append(row)
    return data


def event(report,rule='price_change'):
    return next(e for cat in report['categories'].values() for e in cat['events'] if e['rule_id']==rule)


def outcome(report,rule='price_change',metric='close_change_pct',horizon=1):
    return next(o for o in event(report,rule)['outcomes'] if o['metric']==metric and o['horizon']==horizon)
