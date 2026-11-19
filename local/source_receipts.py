"""Identities of reviewed offline receipts shared by registration, replay and audit."""
import json
import re
from functools import lru_cache

from .core import ROOT
from .dates import timestamp
from .quarterly_observations import quarterly_receipt

ADAPTERS = {
    'tpex-institutional-1': {'tpex_institutional_11856'},
    'tpex-margin-1': {'tpex_margin_11387'},
    'tpex-institutional-2': {'tpex_institutional_11856'},
    'tpex-margin-2': {'tpex_margin_11387'},
    'mops-announcement-1': {'twse-mops-18415', 'tpex-mops-18418'},
    'official-industry-v1': {'mops_industry_20756', 'mops_industry_20757'},
    'official-news-index-v1': {'twse_news_11546', 'fsc_news_6040'},
}


@lru_cache(maxsize=1)
def registry():
    entries = json.loads((ROOT/'local/official_datasets.json').read_text(encoding='utf-8'))
    return {entry['dataset_id']: entry for entry in entries}


def raw_receipt(payload):
    metadata = payload['metadata']
    adapter = metadata.get('adapter_version')
    if adapter not in ADAPTERS:
        return quarterly_receipt(payload)
    source, = payload['sources']
    receipt, = metadata['source_snapshots']
    sid = source['source_id']
    observed = timestamp(metadata['observed_at'])
    if sid not in ADAPTERS[adapter] or receipt['dataset_id'] != sid:
        raise ValueError('offline receipt dataset differs from adapter or source')
    official = registry()[sid]
    if (timestamp(receipt['retrieved_at']) != observed or receipt['resource_url'] != official['resource_url']
            or source.get('catalog', source['url']) != official['dataset_url']
            or source['url'] != official['resource_url' if adapter == 'mops-announcement-1' else 'dataset_url']
            or any(source.get(key) != official[key] for key in ('provider', 'attribution', 'license_url'))
            or type(receipt['bytes']) is not int or receipt['bytes'] <= 0
            or not re.fullmatch('[0-9a-f]{64}', receipt['sha256'])):
        raise ValueError('offline receipt or attribution differs from registered source')
    return (sid, observed), receipt['sha256']


def announcement_locations(payload):
    meta = payload['metadata']
    names = {s['stock_id']: s['name'] for s in payload['stocks']}
    locators = {r['document_id']: r for r in meta['records']}
    if set(locators) != {d['document_id'] for d in payload['documents']} or len(locators) != len(meta['records']):
        raise ValueError('announcement records differ from document identities')
    locations = {}
    for doc in payload['documents']:
        locator = locators[doc['document_id']]
        market, dataset, ticker, _, _ = doc['document_id'].split(':')
        speaker = 'TW:'+ticker
        index = locator['csv_records'][0]
        if doc['source_id'] != f'{market}-mops-{dataset}' or speaker not in names:
            raise ValueError('announcement speaker differs from posting identity')
        locations.setdefault(speaker, (index, '公司代號'))
        approved = [speaker]
        for link in locator.get('reviewed_links', []):
            sid, quote = 'TW:'+link['ticker'], link['evidence']
            field = '主旨' if quote in doc['title'] else '說明'
            if (not quote or (field == '說明' and quote not in doc['content']) or link['name'] not in quote
                    or names.get(sid) != link['name']):
                raise ValueError('announcement reviewed links require quoted identity')
            if 'company_record' in link:
                number = link['company_record']
                if type(number) is not int or not 2 <= number <= meta['raw_row_count'] + 1:
                    raise ValueError('announcement reviewed links need a corroborating company record')
                location = (number, '公司代號')
            else:
                if not re.search(r'(?<![0-9])'+re.escape(link['ticker'])+r'(?![0-9])', quote):
                    raise ValueError('announcement reviewed links require a quoted ticker')
                location = (index, field)
            locations.setdefault(sid, location)
            approved.append(sid)
        if approved != doc['stock_ids']:
            raise ValueError('announcement stock coverage differs from reviewed links')
    return locations


def fallback_stocks(payload):
    """Attach the first identifying source cell for each report-derived company."""
    meta = payload['metadata']
    adapter = meta.get('adapter_version')
    if adapter not in ADAPTERS or 'source_revision' in payload:
        return payload['stocks']
    source, = payload['sources']
    receipt, = meta['source_snapshots']
    locations = {}
    if adapter == 'mops-announcement-1':
        locations = announcement_locations(payload)
    elif adapter == 'official-industry-v1':
        for doc in payload['documents']:
            locations[doc['stock_ids'][0]] = doc['row_number'], '公司代號'
    else:
        for metric in payload.get('chip_metrics', []):
            locations.setdefault(metric['stock_id'], (metric['row_number'], '代號'))
    result = []
    for stock in payload['stocks']:
        row, column = locations[stock['stock_id']]
        result.append(dict(stock, provider=source['provider'], source_id=source['source_id'],
                           source_url=source.get('catalog', source['url']), attribution=source['attribution'],
                           license_url=source['license_url'], raw_sha256=receipt['sha256'],
                           row_number=row, source_column=column))
    return result
