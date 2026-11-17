"""Explicit, snapshot-bound market unit attestations; never infer or convert units."""
from __future__ import annotations
import copy
import re
from urllib.parse import urlsplit
from .dates import iso_date, timestamp

VERSION = 'market-units-2.0'
DEFINITION_KEYS = ('price_unit', 'price_currency', 'volume_unit', 'turnover_unit',
                   'turnover_currency', 'trades_unit', 'price_basis', 'trading_scope',
                   'normalization_version')
VALUE_KEYS = ('open', 'high', 'low', 'close', 'volume_shares', 'turnover_raw', 'trades')
UNKNOWN = (None, '', 'unknown', 'source_reported', 'unspecified')


def apply_review(record, review, source_id, raw_sha256):
    """Return a new record. Evidence is a reviewer's assertion, not authentication."""
    if not isinstance(review, dict) or review.get('schema_version') != 'market-unit-review-1.0':
        raise ValueError('unsupported market unit review')
    if (review.get('source_id') != source_id or review.get('raw_sha256') != raw_sha256
            or review.get('trade_date') != record['trade_date']):
        raise ValueError('market unit review does not match raw source/date')
    symbols = review.get('symbols')
    if (not isinstance(symbols, list) or not symbols or len(symbols) > 10000
            or any(not isinstance(s, str) or not re.fullmatch('[0-9]{4}', s) for s in symbols)
            or len(set(symbols)) != len(symbols) or record['symbol'] not in symbols):
        raise ValueError('market unit review does not cover this symbol')
    iso_date(review['trade_date'])
    if not isinstance(raw_sha256, str) or not re.fullmatch('[0-9a-f]{64}', raw_sha256):
        raise ValueError('invalid market unit review raw hash')
    expected = {'price_unit': 'currency_per_share', 'volume_unit': 'share',
                'turnover_unit': 'currency', 'trades_unit': 'trade', 'price_basis': 'source_unadjusted'}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('market unit review must preserve source scale, shares and unadjusted prices')
    for key in ('price_currency', 'turnover_currency'):
        if not isinstance(review.get(key), str) or not re.fullmatch('[A-Z]{3}', review[key]):
            raise ValueError('market unit review needs explicit currency')
    if review['price_currency'] != review['turnover_currency']:
        raise ValueError('market review cannot convert currency')
    if review.get('trading_scope') not in ('regular_only', 'regular_oddlot_afterhours',
                                          'regular_oddlot_afterhours_block'):
        raise ValueError('market unit review needs explicit trading scope')
    evidence = review.get('evidence')
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 20:
        raise ValueError('market unit review requires bounded evidence')
    for item in evidence:
        if not isinstance(item, dict):
            raise ValueError('invalid market unit evidence')
        url = urlsplit(item.get('url', ''))
        if url.scheme != 'https' or not url.netloc or url.username or url.password:
            raise ValueError('market unit evidence requires HTTPS URL')
        if not re.fullmatch('[0-9a-f]{64}', str(item.get('sha256', ''))):
            raise ValueError('invalid market unit evidence hash')
        if not isinstance(item.get('locator'), str) or not 1 <= len(item['locator']) <= 2000:
            raise ValueError('market unit evidence needs locator')
        timestamp(item.get('retrieved_at'))
    return {**record, **{key: review[key] for key in DEFINITION_KEYS if key != 'normalization_version'},
            'normalization_version': VERSION, 'raw_values': {key: record[key] for key in VALUE_KEYS},
            'unit_review': copy.deepcopy(review)}


def reviewed_record(legacy, saved, source_id, raw_sha256):
    """Rebuild a saved record's exact declared version, including old snapshots."""
    version = saved.get('normalization_version')
    if version is None:
        extras = set(DEFINITION_KEYS) - {"price_unit", "price_basis", "turnover_unit", "normalization_version"}
        if any(key in saved for key in (*extras, "raw_values", "unit_review")):
            raise ValueError("unversioned market unit definition")
        return legacy
    if version != VERSION:
        raise ValueError('unsupported market normalization version')
    return apply_review(legacy, saved.get('unit_review'), source_id, raw_sha256)
