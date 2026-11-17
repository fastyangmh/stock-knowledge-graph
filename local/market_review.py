"""Private market reconciliation against independently transcribed official evidence.

Exact decimals; seven fields per requested security. Unknown definitions, empty
coverage and different trading scopes never pass. No financial metric coercion.
"""
from __future__ import annotations
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation, localcontext
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from .collect_official import atomic_bytes
from .dates import iso_date, timestamp
from .market_graph import read_prices
from .market_prices import _symbols, MAX_BYTES
from .market_units import DEFINITION_KEYS, VALUE_KEYS, UNKNOWN
from .research import guarded
from .research_history import canonical, strict_json, MAX_INPUT_BYTES


def _decimal(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)) or len(str(value)) > 64:
        raise ValueError('market reference requires bounded exact decimal text or integer')
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError('invalid market reference decimal') from exc
    if not result.is_finite() or result < 0:
        raise ValueError('invalid market reference decimal')
    return result


def review(observations, reference, symbols, trade_date, market, *, absolute_tolerance='0'):
    selected = _symbols(symbols)
    if len(selected)*len(VALUE_KEYS) > 20000:
        raise ValueError("market review field budget exceeded")
    iso_date(trade_date)
    tolerance = _decimal(absolute_tolerance)
    if tolerance > Decimal('1000000'):
        raise ValueError('market tolerance exceeds budget')
    if reference.get('schema_version') != 'market-reference-1.0':
        raise ValueError('unsupported market reference schema')
    references = reference.get('records')
    if not isinstance(references, list) or len(references) > 10000:
        raise ValueError('invalid market reference record budget')
    evidence = reference.get('evidence')
    if not isinstance(evidence, list) or len(evidence) > 100:
        raise ValueError('invalid market reference evidence budget')
    evidence_index = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get('id'), str) or item['id'] in evidence_index:
            raise ValueError('invalid or duplicate market evidence identity')
        url = urlsplit(item.get('url', ''))
        if url.scheme != 'https' or not url.netloc or url.username or url.password:
            raise ValueError('market reference needs HTTPS source URL')
        if not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256',''))):
            raise ValueError('invalid market reference evidence hash')
        timestamp(item.get('retrieved_at'))
        evidence_index[item['id']] = item
    indexed = {}
    for record in references:
        if not isinstance(record, dict):
            raise ValueError('market reference row must be an object')
        key = (record.get('symbol'), record.get('trade_date'), record.get('market'))
        if key in indexed:
            raise ValueError('ambiguous duplicate market reference')
        if record.get('evidence_id') not in evidence_index or not isinstance(record.get('locator'), str) or not record['locator']:
            raise ValueError('market reference needs evidence and row/column locator')
        indexed[key] = record
    actual = {}
    for item in observations:
        record = item['record']
        if record['symbol'] in actual or record['symbol'] not in selected or record['trade_date'] != trade_date or record['market'] != market:
            raise ValueError('market review observation scope mismatch')
        actual[record['symbol']] = item
    rows=[]
    for symbol in sorted(selected):
        item=actual.get(symbol); left=item['record'] if item else None
        right=indexed.get((symbol,trade_date,market))
        for field in VALUE_KEYS:
            row={'symbol':symbol,'trade_date':trade_date,'market':market,'field':field,
                 'status':'missing_input' if left is None else 'missing_reference',
                 'difference':None,'allowed_difference':str(tolerance),
                 'input':left.get(field) if left else None,'reference':right.get(field) if right else None,
                 'input_raw_sha256':item.get('raw_sha256') if item else None,
                 'reference_evidence':evidence_index[right['evidence_id']] if right else None,
                 'reference_locator':right['locator'] if right else None,
                 'input_definition':{k:left.get(k) for k in DEFINITION_KEYS} if left else None,
                 'reference_definition':{k:right.get(k) for k in DEFINITION_KEYS} if right else None}
            if left is not None and right is not None:
                keys=DEFINITION_KEYS[:-1]  # independently prepared reference need not share producer version
                if item.get('raw_snapshot_verified') is not True:
                    row['status']='unverified_input_snapshot'
                elif item.get('raw_sha256') == evidence_index[right['evidence_id']]['sha256']:
                    row['status']='not_independent_reference'
                elif any(left.get(k) in UNKNOWN or right.get(k) in UNKNOWN for k in keys):
                    row['status']='definition_unverified'
                elif any(left.get(k) != right.get(k) for k in keys):
                    row['status']='definition_mismatch'
                elif left.get(field) is None or right.get(field) is None:
                    row['status']='missing_value'
                else:
                    x,y=_decimal(left[field]),_decimal(right[field])
                    with localcontext() as ctx:
                        ctx.prec=160
                        delta=x-y
                    row.update(difference=format(delta,'f'), status='equal' if delta==0 else
                               'within_tolerance' if abs(delta)<=tolerance else 'value_mismatch')
            rows.append(row)
    counts=dict(sorted(Counter(row['status'] for row in rows).items()))
    compared=sum(counts.get(k,0) for k in ('equal','within_tolerance','value_mismatch'))
    return {'schema_version':'market-review-1.0','market':market,'trade_date':trade_date,
            'symbols':sorted(selected),'sample_count':len(selected),'rows':rows,'counts':counts,
            'compared_fields':compared,'required_fields':len(selected)*len(VALUE_KEYS),
            'needs_review':compared==0 or any(r['status'] not in ('equal','within_tolerance') for r in rows),
            'absolute_tolerance':str(tolerance),
            'scope':'independent_numeric_reconciliation_not_authentication_or_price_adjustment',
            'reference_document_sha256':hashlib.sha256(canonical(reference)).hexdigest()}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db',type=Path,required=True)
    p.add_argument('--snapshots',type=Path,required=True)
    p.add_argument('--market',choices=('twse','tpex'),required=True)
    p.add_argument('--symbols',nargs='+',required=True)
    p.add_argument('--trade-date',required=True)
    p.add_argument('--known-at',required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--absolute-tolerance',default='0')
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    database,snapshots,reference_path,output=map(guarded,(args.db,args.snapshots,args.reference,args.output))
    if output in (database,reference_path) or output.is_relative_to(snapshots):
        raise ValueError('review output must not overwrite input evidence')
    with reference_path.open('rb') as f: body=f.read(MAX_INPUT_BYTES+1)
    reference=strict_json(body)
    # Read-only evidence hash verification: no HTTP, traversal, symlinks or oversized reads.
    total=0
    evidence_items=reference.get("evidence")
    if not isinstance(evidence_items, list) or len(evidence_items)>100:
        raise ValueError("invalid market reference evidence budget")
    for evidence in evidence_items:
        relative=Path(evidence.get('path',''))
        if relative.is_absolute() or len(relative.parts)!=1 or relative.name in ('.','..',''):
            raise ValueError('market reference evidence must be a sibling file')
        path=guarded(reference_path.parent/relative)
        if output==path:
            raise ValueError('review output must not overwrite reference evidence')
        with path.open('rb') as f: raw=f.read(MAX_BYTES+1)
        total+=len(raw)
        if len(raw)>MAX_BYTES or total>128*1024*1024:
            raise ValueError('market reference evidence exceeds byte budget')
        if hashlib.sha256(raw).hexdigest()!=evidence.get('sha256'):
            raise ValueError('market reference evidence checksum mismatch')
    observations=read_prices(database,args.market,args.symbols,args.trade_date,args.known_at,snapshots)
    result=review(observations,reference,args.symbols,args.trade_date,args.market.upper(),absolute_tolerance=args.absolute_tolerance)
    result['reference_file_sha256']=hashlib.sha256(body).hexdigest()
    encoded=canonical(result)
    if len(encoded)>MAX_INPUT_BYTES:
        raise ValueError("market review report exceeds byte budget")
    atomic_bytes(output,encoded)
    print(json.dumps({key:result[key] for key in ('counts','compared_fields','needs_review')}))
    return 2 if result['needs_review'] else 0


if __name__=='__main__':
    raise SystemExit(main())
