"""Convert one reviewed quarterly CSV and its private acquisition manifest to research input."""
import argparse
import calendar
import csv
import hashlib
import re
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from .collect_official import atomic_bytes
from .dates import timestamp
from .official_adapter import csv_rows, number, report_date
from . import quarterly_balance, quarterly_income
from .quarterly_review import apply_review
from .research import guarded
from .research_history import MAX_INPUT_BYTES, canonical, strict_json_value, validate_payload, validate_symbols
from .safety import exclusive_lock


SOURCES = {**quarterly_income.SOURCES, **quarterly_balance.SOURCES}
ADDITIONAL_FIELDS = {'income': quarterly_income.ADDITIONAL_FIELDS, 'balance': quarterly_balance.ADDITIONAL_FIELDS}


def read_bytes(path, limit=MAX_INPUT_BYTES):
    with path.open('rb') as stream:
        body = stream.read(limit + 1)
    if not body or len(body) > limit:
        raise ValueError(f'{path.name}: quarterly file empty or exceeds byte budget')
    return body


def load_source(manifest, dataset):
    rows = strict_json_value(read_bytes(manifest, 4 * 1024 * 1024))
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise ValueError('invalid quarterly acquisition manifest')
    entries = [r for r in rows if r.get('id') == dataset]
    if len(entries) != 1:
        raise ValueError(f'{dataset}: expected one acquisition entry')
    entry = entries[0]
    filename, market, sector, statement, fields = SOURCES[dataset]
    catalog = f'https://data.gov.tw/dataset/{dataset}'
    resource = 'https://mopsfin.twse.com.tw/opendata/' + filename
    if (entry.get('catalog') != catalog or entry.get('url') != resource or
            entry.get('status') != '200' or type(entry.get('exit')) is not int or entry['exit'] != 0):
        raise ValueError(f'{dataset}: unapproved resource or unsuccessful acquisition')
    raw = read_bytes(guarded(manifest.parent / f'{dataset}.response'))
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != entry.get('sha256') or len(raw) != entry.get('bytes'):
        raise ValueError(f'{dataset}: raw checksum/size mismatch')
    provider = '金融監督管理委員會證券期貨局'
    source = dict(source_id=f'mops_{dataset}', provider=provider, url=catalog, resource_url=resource,
                  license_type='OGDL-1.0', license_url='https://data.gov.tw/license',
                  attribution=f'{provider}，政府資料開放平臺資料集 {dataset}', market=market,
                  sector=sector, statement=statement)
    try:
        records = csv_rows(raw, strict=True)
    except csv.Error as exc:
        raise ValueError(f'{dataset}: invalid CSV: {exc}') from exc
    return records, source, fields, timestamp(entry['received_at']), checksum


def period_end(row):
    if not re.fullmatch(r'[0-9]{3}', row['年度']) or row['季別'] not in ('1', '2', '3', '4'):
        raise ValueError('expected ROC year and quarter 1..4')
    year, month = int(row['年度']) + 1911, int(row['季別']) * 3
    return date(year, month, calendar.monthrange(year, month)[1])


def normalize(manifest, dataset, symbols):
    selected = validate_symbols(symbols)
    rows, source, fields, received, checksum = load_source(manifest, dataset)
    required = {'出表日期', '年度', '季別', '公司代號', '公司名稱', *fields}
    absent = required.difference(rows[0])
    if absent:
        raise ValueError(f'{dataset}: missing quarterly fields: ' + ', '.join(sorted(absent)))
    required.update(ADDITIONAL_FIELDS[source['statement']][source['sector']])
    unknown = rows[0].keys() - required
    if unknown:
        raise ValueError(f'{dataset}: unknown quarterly fields: ' + ', '.join(sorted(unknown)))
    if not required.issubset(rows[0]):
        raise ValueError(f'{dataset}: missing published fields, quarterly schema review required')
    report_basis = 'point_in_time' if source['statement'] == 'balance' else None
    sid = source['source_id']
    stocks, documents, metrics, missing = {}, [], [], []
    dates = set()
    received_day = received.astimezone(ZoneInfo('Asia/Taipei')).date()
    for index, row in enumerate(rows, 1):
        code = row['公司代號']
        if not code:
            if any(v for k,v in row.items() if k != '出表日期'):
                raise ValueError(f'{dataset}: incomplete identity at record {index}')
            continue
        period, reported = period_end(row), report_date(row['出表日期'])
        if not period <= reported <= received_day:
            raise ValueError(f'{dataset}: inconsistent period, report or retrieval date at record {index}')
        dates.add((period, reported))
        stock_id = f'TW:{code}'
        if stock_id not in selected:
            continue
        if stock_id in stocks or not row['公司名稱']:
            raise ValueError(f'{dataset}: duplicate or unnamed company at record {index}')
        provenance = dict(source_id=sid, source_url=source['url'], attribution=source['attribution'],
                          license_url=source['license_url'])
        stocks[stock_id] = dict(stock_id=stock_id, ticker=code, market='TW', name=row['公司名稱'], **provenance)
        doc_id = f'{sid}:{code}:{period.isoformat()}'
        title = f'{row["公司名稱"]} {period.year} Q{row["季別"]} {source["statement"]}'
        documents.append(dict(document_id=doc_id, external_id=doc_id, title=title, content=title,
                              doc_type='financial', stock_ids=[stock_id], period_end=period.isoformat(),
                              published_at=received.isoformat(), available_at=received.isoformat(),
                              availability_basis='observed_at_retrieval_not_original_publication',
                              source_report_date=reported.isoformat(), **provenance))
        for field, (metric, measure) in fields.items():
            location = dict(stock_id=stock_id, source_field=field, source_record=index,
                            raw_value=row[field], period_end=period.isoformat())
            try:
                value = number(row[field])
            except ValueError as exc:
                raise ValueError(f'{dataset}: record {index}, {field}: {exc}') from exc
            if value is None:
                missing.append(location)
                continue
            metrics.append(dict(**location, metric=metric, measure=measure, source_id=sid,
                                raw_sha256=checksum, normalization_version='mops-quarterly-v1',
                                source_report_date=reported.isoformat(), source_year=row['年度'],
                                source_quarter=row['季別'], period_end_basis='calendar_quarter_end',
                                period_type='quarter', value=value, unit='source_reported',
                                currency=None, report_basis=report_basis, statement_scope=None,
                                available_at=received.isoformat()))
    if len(dates) > 1:
        raise ValueError(f'{dataset}: mixed quarterly periods or report dates')
    if stocks.keys() != selected:
        raise ValueError(f'{dataset}: no observation for ' + ', '.join(sorted(selected - stocks.keys())))
    empty = selected - {row['stock_id'] for row in metrics}
    if empty:
        raise ValueError(f'{dataset}: no numeric observation for ' + ', '.join(sorted(empty)))
    return dict(stocks=list(stocks.values()), sources=[source], documents=documents,
                financial_metrics=metrics, chip_metrics=[],
                metadata=dict(adapter_version='mops-quarterly-v1', observed_at=received.isoformat(),
                              source_snapshots=[dict(dataset_id=sid, resource_url=source['resource_url'],
                                                     retrieved_at=received.isoformat(), sha256=checksum)],
                              missing_values=missing, research_selection=dict(
                                  mode='explicit_symbols_not_index_membership', stock_ids=sorted(selected))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--dataset', required=True, type=int, choices=sorted(SOURCES))
    parser.add_argument('--symbols', required=True, nargs='+')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--review', type=Path, help='Private dated issuer cell review')
    args = parser.parse_args(argv)
    output, manifest = guarded(args.output), guarded(args.manifest)
    payload = normalize(manifest, args.dataset, args.symbols)
    if args.review:
        apply_review(payload, args.dataset, read_bytes(guarded(args.review), 4 * 1024 * 1024))
    write_normalized(payload, output)


def write_normalized(payload, output):
    validate_payload(payload)
    data = canonical(payload) + b'\n'
    with exclusive_lock(output):
        if output.exists() and (output.stat().st_size != len(data) or output.read_bytes() != data):
            raise ValueError('use a new quarterly output path for changed input')
        atomic_bytes(output, data)
    print(f'Normalized {len(payload["financial_metrics"])} quarterly metrics in {output}')


if __name__ == '__main__':
    main()
