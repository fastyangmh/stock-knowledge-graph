"""Normalize reviewed daily MOPS announcement CSVs for private research."""
import argparse
import csv
import hashlib
import io
import re
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

from .calendar_archive import MIB, bounded_bytes
from .collect_official import atomic_bytes
from .dates import timestamp
from .official_adapter import report_date
from .offline_receipt import read_receipt
from .research import guarded
from .research_history import MAX_INPUT_BYTES, canonical, strict_json, validate_payload
from .safety import exclusive_lock

MARKETS = {18415: 'twse', 18418: 'tpex'}
FIELDS = ['出表日期', '發言日期', '發言時間', '公司代號', '公司名稱', '主旨', '符合條款', '事實發生日', '說明']
TAIPEI = ZoneInfo('Asia/Taipei')


def parse_row(row, market, dataset, received):
    if len(row) != len(FIELDS) or any(not value.strip() or '\x00' in value for value in row):
        raise ValueError('expected nine nonempty text fields')
    report, day, clock, ticker, name, title, clause, event, body = row
    if not re.fullmatch('[0-9]{4}', ticker) or not re.fullmatch('[0-9]{1,6}', clock):
        raise ValueError('invalid company code or announcement time')
    if not all(re.fullmatch('[0-9]{7}', value) for value in (day, report, event)):
        raise ValueError('expected ROC dates')
    clock = clock.zfill(6)
    published = datetime.combine(report_date(day), time(int(clock[:2]), int(clock[2:4]), int(clock[4:])), TAIPEI)
    if published > received or not published.date() <= report_date(report) <= received.astimezone(TAIPEI).date():
        raise ValueError('publication or report date conflicts with receipt')
    doc_id = f'{market}:{dataset}:{ticker}:{day}:{clock}'
    doc = dict(document_id=doc_id, external_id=doc_id, doc_type='news', stock_ids=['TW:'+ticker],
               title=title, content=body, published_at=published.isoformat(), source_report_date=report_date(report).isoformat())
    stock = dict(stock_id='TW:'+ticker, market='TW', ticker=ticker, name=name)
    locator = dict(document_id=doc_id, event_date=report_date(event).isoformat(), clause=clause,
                   source_report_date=doc['source_report_date'], csv_records=[])
    return stock, doc, locator


def apply_revision(payload, revision, parent_path, record):
    if (not isinstance(revision, dict) or set(revision) !=
            {'action', 'evidence', 'target_document_id', 'target_snapshot_sha256'}):
        raise ValueError('invalid reviewed revision fields')
    parent = strict_json(bounded_bytes(guarded(parent_path), MAX_INPUT_BYTES))
    validate_payload(parent)
    if hashlib.sha256(canonical(parent)).hexdigest() != revision['target_snapshot_sha256']:
        raise ValueError('reviewed parent checksum mismatch')
    doc, = payload['documents']
    did, quote = revision['target_document_id'], revision['evidence']
    if (not isinstance(quote, str) or not quote.strip() or not any(quote in doc[k] for k in ('title', 'content'))
            or not isinstance(did, str) or did.rsplit(':', 2)[0] != doc['document_id'].rsplit(':', 2)[0]
            or did == doc['document_id']):
        raise ValueError('revision needs an earlier target from the same issuer and exact source quotation')
    source, = payload['sources']
    if not any(all(s.get(k) == source[k] for k in ('source_id', 'provider', 'url')) for s in parent['sources']):
        raise ValueError('revision parent source differs')
    prior_notice = parent.get('source_revision')
    if prior_notice:
        if prior_notice['group'] != 'documents' or prior_notice['key'] != {'document_id': did}:
            raise ValueError('parent notice targets a different document')
        links = [s['stock_id'] for s in parent['stocks']]
        last_published = prior_notice['published_at']
    else:
        if any(d['document_id'] == doc['document_id'] for d in parent['documents']):
            raise ValueError('parent already includes notice as a standalone posting')
        targets = [d for d in parent['documents'] if d['document_id'] == did and d['source_id'] == doc['source_id']]
        if len(targets) != 1:
            raise ValueError('reviewed parent document is absent')
        links, last_published = targets[0]['stock_ids'], targets[0]['published_at']
    if doc['stock_ids'][0] not in links or timestamp(last_published) >= timestamp(doc['published_at']):
        raise ValueError('revision precedes its target or differs in issuer')
    payload['stocks'] = [s for s in parent['stocks'] if s['stock_id'] in links]
    doc['document_id'], doc['stock_ids'] = did, sorted(links)
    if revision['action'] == 'withdraw':
        payload['documents'] = []
    payload['source_revision'] = dict(schema_version='source-revision-1', group='documents',
        key=dict(document_id=did), source_id=source['source_id'], action=revision['action'],
        target_snapshot_sha256=revision['target_snapshot_sha256'], published_at=doc['published_at'],
        effective_at=doc['published_at'], evidence=quote, source_reference=source['url']+f' # csv record {record}')


def apply_review(payload, review, record, parent, companies):
    metadata = payload['metadata']
    field = 'revision' if parent is not None else 'links'
    if (set(review) != {'raw_sha256', 'record', field}
            or type(review['record']) is not int or review['record'] != record
            or review['raw_sha256'] != metadata['source_snapshots'][0]['sha256']):
        raise ValueError('review must identify the exact receipt and selected record')
    if parent is not None:
        apply_revision(payload, review['revision'], parent, record)
        return
    doc, = payload['documents']
    links = review['links']
    if not isinstance(links, list):
        raise ValueError('expected a reviewed links array')
    for link in links:
        required = {'ticker', 'name', 'evidence'}
        if (not isinstance(link, dict) or set(link) not in (required, required | {'company_record'})
                or not all(isinstance(link[k], str) and link[k].strip() for k in required)):
            raise ValueError('expected a company link with name, ticker and quoted evidence')
        ticker, name, quote = link['ticker'], link['name'], link['evidence']
        if (not re.fullmatch('[0-9]{4}', ticker) or 'TW:'+ticker in doc['stock_ids']
                or name not in quote
                or not any(quote in doc[k] for k in ('title', 'content'))):
            raise ValueError('company link requires its exact name in a source quotation')
        if 'company_record' in link:
            number = link['company_record']
            if type(number) is not int or companies.get(number) != (ticker, name):
                raise ValueError('reviewed company record does not confirm ticker and name')
        elif not re.search(r'(?<![0-9])'+ticker+r'(?![0-9])', quote):
            raise ValueError('company link needs its ticker in the quote or a reviewed company record')
        doc['stock_ids'].append('TW:'+ticker)
        payload['stocks'].append(dict(stock_id='TW:'+ticker, market='TW', ticker=ticker, name=name))
    metadata['records'][0]['reviewed_links'] = links


def normalize(manifest, dataset, record, review, parent):
    market = MARKETS[dataset]
    source_id = f'{market}-mops-{dataset}'
    source, receipt, body = read_receipt(manifest, source_id, dataset)
    observed = receipt['received_at']
    received = timestamp(observed)
    rows = csv.reader(io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
    if next(rows, None) != FIELDS:
        raise ValueError(f'unsupported {dataset} announcement header')
    stocks, documents, locators, originals = {}, {}, {}, {}
    raw_count = 0
    companies = {}
    for index, row in enumerate(rows, 2):
        raw_count += 1
        try:
            stock, doc, locator = parse_row(row, market, dataset, received)
        except ValueError as exc:
            raise ValueError(f'{dataset} row {index}: {exc}') from exc
        did, sid = doc['document_id'], stock['stock_id']
        if did in originals and originals[did] != row:
            raise ValueError(f'{dataset} row {index}: conflicting same-time announcement')
        if sid in stocks and stock != stocks[sid]:
            raise ValueError(f'{dataset} row {index}: conflicting company identity')
        stocks[sid] = stock
        companies[index] = (stock['ticker'], stock['name'])
        originals[did] = row
        documents[did] = dict(**doc, source_id=source_id, available_at=observed, source_url=source['dataset_url'],
                              attribution=source['attribution'], license_url=source['license_url'])
        locators.setdefault(did, locator)['csv_records'].append(index)
    if not documents:
        raise ValueError('empty announcement selection')
    if record is not None:
        if not 2 <= record <= raw_count + 1:
            raise ValueError('record outside the saved CSV')
        did, = (key for key, loc in locators.items() if record in loc['csv_records'])
        documents, locators = {did: documents[did]}, {did: locators[did]}
        sid, = documents[did]['stock_ids']
        stocks = {sid: stocks[sid]}
    provenance = dict(source_id=source_id, provider=source['provider'], url=source['resource_url'],
                      catalog=source['dataset_url'], license_type='OGDL-1.0', license_url=source['license_url'],
                      attribution=source['attribution'], usage=source['usage'])
    snapshot = dict(dataset_id=source_id, sha256=receipt['sha256'], bytes=receipt['bytes'],
                    retrieved_at=observed, resource_url=source['resource_url'])
    metadata = dict(adapter_version='mops-announcement-1', observed_at=observed, source_snapshots=[snapshot],
                    raw_row_count=raw_count, records=list(locators.values()))
    payload = dict(stocks=list(stocks.values()), sources=[provenance], documents=list(documents.values()),
                   financial_metrics=[], chip_metrics=[], metadata=metadata)
    if review is not None:
        apply_review(payload, review, record, parent, companies)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--dataset', type=int, choices=MARKETS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--record', type=int, help='logical CSV record, with header numbered 1')
    parser.add_argument('--review', type=Path, help='private reviewed links or revision for one selected record')
    parser.add_argument('--parent', type=Path, help='previous normalized snapshot of a reviewed revision')
    args = parser.parse_args(argv)
    output, manifest = guarded(args.output), guarded(args.manifest)
    if output.is_relative_to(manifest.parent):
        raise ValueError('normalized output must be outside the saved capture directory')
    review = None
    if args.parent is not None and (args.review is None or guarded(args.parent) == output):
        raise ValueError('a revision parent requires a review and a new output')
    if args.review is not None:
        if args.record is None or guarded(args.review) == output:
            raise ValueError('review requires one selected record and a separate output')
        review = strict_json(bounded_bytes(guarded(args.review), MIB))
    payload = normalize(manifest, args.dataset, args.record, review, args.parent)
    validate_payload(payload)
    data = canonical(payload)
    with exclusive_lock(output):
        if output.exists():
            if output.stat().st_size != len(data) or output.read_bytes() != data:
                raise ValueError('changed announcement selection requires a new output path')
        else:
            atomic_bytes(output, data)
    print('Private announcement import:', len(payload['documents']), 'documents')


if __name__ == '__main__':
    main()

