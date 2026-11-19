"""Attach a dated issuer review only to the selected source cells it identifies."""
import hashlib
import re
from decimal import Decimal
from fractions import Fraction
from urllib.parse import urlsplit

from .dates import timestamp
from .research_history import strict_json


def exact_value(value):
    if not isinstance(value, str) or len(value) > 64 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', value):
        raise ValueError('quarterly review requires exact decimal text')
    return Fraction(Decimal(value))


def apply_review(payload, dataset, body):
    review = strict_json(body)
    snapshot = payload['metadata']['source_snapshots'][0]
    if (review.get('schema_version') != 'quarterly-review-v1' or review.get('dataset') != dataset
            or review.get('raw_sha256') != snapshot['sha256']):
        raise ValueError('quarterly review does not match dataset/raw checksum')
    reviewed = timestamp(review['reviewed_at'])
    if reviewed < timestamp(snapshot['retrieved_at']):
        raise ValueError('review of this snapshot predates acquisition')
    candidates = {(r['stock_id'], r['period_end'], r['source_field']): r for r in payload['financial_metrics']}
    rows = review.get('rows')
    if not isinstance(rows, list) or not 1 <= len(rows) <= len(candidates):
        raise ValueError('quarterly review requires identified source cells')
    source = payload['sources'][0]
    for item in rows:
        key = (item['stock_id'], item['period_end'], item['source_field'])
        row = candidates.pop(key, None)
        if row is None:
            raise ValueError('unresolved or duplicate quarterly review cell')
        reference = urlsplit(item['reference_url'])
        if (reference.scheme != 'https' or not reference.hostname or reference.hostname in
                {urlsplit(source[k]).hostname for k in ('url', 'resource_url')} or
                not isinstance(item['locator'], str) or not item['locator'].strip()):
            raise ValueError('quarterly review requires independent issuer URL and field locator')
        bases = ('point_in_time',) if source['statement'] == 'balance' else ('cumulative', 'single_period')
        if item['statement_scope'] not in ('consolidated', 'separate') or item['report_basis'] not in bases:
            raise ValueError('unsupported reviewed quarterly statement scope or basis')
        scales = ({'TWD_per_share': 1} if row['measure'] == 'per_share' else
                  {'TWD': 1, 'TWD_thousands': 1000, 'TWD_millions': 1000000})
        if item['raw_unit'] not in scales or item['reference_unit'] not in scales:
            raise ValueError('reviewed unit is incompatible with source field measure')
        actual = exact_value(row['raw_value'].replace(',', '')) * scales[item['raw_unit']]
        expected = exact_value(item['reference_value']) * scales[item['reference_unit']]
        status = 'equal' if actual == expected else 'value_mismatch'
        row['available_at'] = reviewed.isoformat()
        row['issuer_review'] = {**item, 'status': status, 'reviewed_at': reviewed.isoformat()}
        if actual == expected:
            row.update(unit=item['raw_unit'], currency='TWD', statement_scope=item['statement_scope'],
                       report_basis=item['report_basis'])
    payload['metadata'].update(reviewed_at=reviewed.isoformat(), review_sha256=hashlib.sha256(body).hexdigest())
