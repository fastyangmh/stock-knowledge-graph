"""Reusable synthetic real-bundle fixtures for the history/compare tests."""
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from local.research import run
from local.research_history import canonical
from test_alerts import payload


def make_run(root, n=1, *, config=None, alerts=True, value=30, source='fixture', missing=False, symbols=None):
    root=Path(root)
    known=(datetime(2020,8,16,tzinfo=timezone.utc)+timedelta(days=n)).isoformat()
    data=payload()
    data['metadata']['observed_at']=known
    data['sources'][0]['source_id']=source
    for metric in data['financial_metrics']:
        metric['source_id']=source
        metric['available_at']=known
        if metric['metric']=='monthly_revenue_yoy_pct' and metric['period_end']=='2020-07-31':metric['value']=value
    if missing:data['financial_metrics']=[m for m in data['financial_metrics'] if m['metric']=='monthly_revenue']
    if symbols and '1001' in symbols:data['stocks'].append({'stock_id':'TW:1001','ticker':'1001','market':'TW','name':'Synthetic B'})
    path=root/f'input-{n}.json';path.write_bytes(canonical(data))
    with patch('local.research.utc_now',return_value=known),patch('local.research_history.utc_now',return_value=known):
        return run(path,symbols or ['1000'],history_db=root/f'history-{n}.db',output_root=root/'runs',
                   alerts=alerts,alerts_config=config)
