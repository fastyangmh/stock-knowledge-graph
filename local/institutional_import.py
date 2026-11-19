"""Normalize a saved TPEx 11856 official CSV into private daily institutional observations."""
import argparse
import base64
import csv
import io
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from .dates import iso_date, timestamp
from .official_adapter import report_date
from .offline_receipt import normalized_destination, read_receipt, write_normalized
from .research_history import validate_symbols

SOURCE = 'tpex_institutional_11856'
GROUPS = {
    'foreign_ex_dealers': '外資及陸資不含外資自營商', 'foreign_dealers': '外資自營商',
    'foreign_total': '外資及陸資', 'investment_trust': '投信',
    'dealer_proprietary': '自營商自行買賣', 'dealer_hedging': '自營商避險', 'dealer_total': '自營商',
}
SIDES = {'buy': '買進股數', 'sell': '賣出股數', 'net': '買賣超股數'}
METRICS = {group+'_'+side: label+suffix for group, label in GROUPS.items() for side, suffix in SIDES.items()}
METRICS['institutions_net'] = '三大法人買賣超股數合計'
COLUMNS = ['資料日期', '代號', '名稱', *METRICS.values()]


def _shares(raw, column, row_number):
    value = raw.strip()
    signed = '買賣超' in column
    if not re.fullmatch(r'[+-]?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)', value):
        raise ValueError(f'11856 row {row_number} {column}: expected integer share count')
    parsed = int(value.replace(',', ''))
    if (not signed and parsed < 0) or abs(parsed) > 2**53 - 1:
        raise ValueError(f'11856 row {row_number} {column}: invalid or inexact share count')
    return parsed


def _check_subtotals(values, row_number):
    for group in GROUPS:
        net = group+'_net'
        if values[group+'_buy'] - values[group+'_sell'] != values[net]:
            raise ValueError(f'11856 row {row_number} {METRICS[net]}: buy minus sell mismatch')
    # These two subtotal identities were checked against every official row.
    # The source total has an unresolved inclusion rule and stands on its own.
    subtotals = (('foreign_total', 'foreign_ex_dealers', 'foreign_dealers'),
                 ('dealer_total', 'dealer_proprietary', 'dealer_hedging'))
    for total, first, second in subtotals:
        for side in SIDES:
            key = total+'_'+side
            if values[first+'_'+side] + values[second+'_'+side] != values[key]:
                raise ValueError(f'11856 row {row_number} {METRICS[key]}: subtotal mismatch')


def row_values(row, index):
    values = {key: _shares(raw, column, index) for (key, column), raw in zip(METRICS.items(), row[3:])}
    _check_subtotals(values, index)
    return values


def normalize(manifest, trade_date, selection):
    source, receipt, body = read_receipt(manifest, SOURCE, 11856)
    return project(source, receipt, body, trade_date, selection)


def project(source, receipt, body, trade_date, selection):
    target = iso_date(trade_date)
    observed = receipt['received_at']
    if target > timestamp(observed).astimezone(ZoneInfo('Asia/Taipei')).date():
        raise ValueError('11856 trading date follows receipt')
    reader = csv.reader(io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader, None) != COLUMNS:
        raise ValueError('unsupported 11856 CSV header')
    origin = dict(source_id=SOURCE, source_url=source['dataset_url'],
                  attribution=source['attribution'], license_url=source['license_url'])
    stocks, docs, metrics, seen = [], [], [], set()
    for index, row in enumerate(reader, 2):
        if len(row) != len(COLUMNS) or report_date(row[0].strip()) != target:
            raise ValueError(f'11856 row {index}: row width or trading date mismatch')
        symbol, name = row[1].strip(), row[2].strip()
        if not re.fullmatch(r'[0-9A-Za-z]{4,12}', symbol) or not name or symbol in seen:
            raise ValueError(f'11856 row {index}: invalid or duplicate security')
        seen.add(symbol)
        values = row_values(row, index)
        sid = 'TW:'+symbol
        if sid not in selection:
            continue
        stocks.append(dict(stock_id=sid, market='TW', ticker=symbol, name=name, provider=source['provider'],
                           raw_sha256=receipt['sha256'], row_number=index, source_column='代號', **origin))
        document_id = f'{SOURCE}:{symbol}:{trade_date}'
        docs.append(dict(document_id=document_id, external_id=document_id, doc_type='chip_report',
                         title=f'{name} {trade_date} 三大法人買賣明細',
                         content=f'{name} 的法人買賣明細取自櫃買中心，以原始欄名區分法人類別、買進、賣出及買賣超。',
                         stock_ids=[sid], published_at=observed, available_at=observed,
                         availability_basis='observed_at_retrieval_not_original_publication', **origin))
        for key, value in values.items():
            metrics.append(dict(stock_id=sid, source_id=SOURCE, metric='tpex_institutional_'+key,
                                trade_date=trade_date, value=value, unit='shares', available_at=observed,
                                raw_sha256=receipt['sha256'], row_number=index, source_column=METRICS[key]))
    if {s['stock_id'] for s in stocks} != selection:
        raise ValueError('11856 incomplete coverage for selected stocks')
    provenance = dict(source_id=SOURCE, provider=source['provider'], url=source['dataset_url'],
                      license_type='OGDL-1.0', license_url=source['license_url'], attribution=source['attribution'],
                      usage=source['usage'], market='TPEX', independent_reference_status='needs-info')
    metadata = dict(adapter_version='tpex-institutional-2', observed_at=observed, trade_date=trade_date,
                    raw_row_count=len(seen), source_snapshots=[dict(dataset_id=SOURCE, sha256=receipt['sha256'],
                    bytes=receipt['bytes'], retrieved_at=observed, resource_url=source['resource_url'])])
    return dict(source_csv_b64=base64.b64encode(body).decode('ascii'), stocks=stocks, sources=[provenance], documents=docs, financial_metrics=[], chip_metrics=metrics,
                metadata=metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--symbols', required=True, nargs='+')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    output = normalized_destination(args.output, args.manifest)
    payload = normalize(args.manifest, args.trade_date, validate_symbols(args.symbols))
    write_normalized(output, payload)
    print('Private institutional import:', len(payload['stocks']), 'stocks,', len(payload['chip_metrics']), 'observations')


if __name__ == '__main__':
    main()
