"""Import a dated, saved TPEx margin trading receipt into private daily research."""
import argparse
import base64
import csv
import io
import re
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .dates import iso_date, timestamp
from .official_adapter import report_date
from .offline_receipt import normalized_destination, read_receipt, write_normalized
from .research_history import validate_symbols

SOURCE = 'tpex_margin_11387'
METRICS = {
    '前資餘額': 'financing_previous_balance', '資買': 'financing_buy', '資賣': 'financing_sell',
    '現償': 'financing_repayment', '資餘額': 'financing_balance', '資屬證金': 'financing_finance_company_balance',
    '資使用率': 'financing_utilization', '資限額': 'financing_limit', '前券餘額': 'short_previous_balance',
    '券賣': 'short_sell', '券買': 'short_buy', '券償': 'short_repayment', '券餘額': 'short_balance',
    '券屬證金': 'short_finance_company_balance', '券使用率': 'short_utilization', '券限額': 'short_limit',
    '資券相抵': 'offset',
}
COLUMNS = ['資料日期', '代號', '名稱', *METRICS, '備註']


def row_values(row, index):
    values = {}
    for column, raw in zip(METRICS, row[3:-1]):
        raw = raw.strip()
        if column.endswith('使用率'):
            if not re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,2})?', raw):
                raise ValueError(f'11387 row {index} {column}: expected percentage')
            values[column] = float(raw)
        else:
            if not re.fullmatch(r'[0-9]{1,16}', raw) or int(raw) > 2**53 - 1:
                raise ValueError(f'11387 row {index} {column}: expected nonnegative exact integer')
            values[column] = int(raw)
    if values['前資餘額'] + values['資買'] - values['資賣'] - values['現償'] != values['資餘額']:
        raise ValueError(f'11387 row {index} 資餘額: financing balance does not reconcile')
    if values['前券餘額'] + values['券賣'] - values['券買'] - values['券償'] != values['券餘額']:
        raise ValueError(f'11387 row {index} 券餘額: short balance does not reconcile')
    for side in ('資', '券'):
        limit, balance, utilization = side+'限額', side+'餘額', side+'使用率'
        # Published percentages have up to two decimals. Preserve the source's
        # number even when it truncates rather than rounds the last digit.
        if values[limit]:
            reported = Decimal(str(values[utilization]))
            calculated = Decimal(100 * values[balance]) / values[limit]
            if abs(reported - calculated) >= Decimal('0.01'):
                raise ValueError(f'11387 row {index} {utilization}: inconsistent percentage')
    return values


def normalize(manifest, trade_date, selection):
    source, receipt, body = read_receipt(manifest, SOURCE, 11387)
    return project(source, receipt, body, trade_date, selection)


def project(source, receipt, body, trade_date, selection):
    observed = receipt['received_at']
    target = iso_date(trade_date)
    if target > timestamp(observed).astimezone(ZoneInfo('Asia/Taipei')).date():
        raise ValueError('11387 trading date follows receipt')
    reader = csv.reader(io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader, None) != COLUMNS:
        raise ValueError('11387 unsupported CSV header')
    origin = dict(source_id=SOURCE, source_url=source['dataset_url'],
                  attribution=source['attribution'], license_url=source['license_url'])
    stocks, documents, metrics, seen = [], [], [], set()
    for index, row in enumerate(reader, 2):
        if len(row) != len(COLUMNS) or report_date(row[0].strip()) != target:
            raise ValueError(f'11387 row {index}: row width or trading date mismatch')
        symbol, name = row[1].strip(), row[2].strip()
        if not re.fullmatch(r'[0-9A-Za-z]{4,12}', symbol) or not name or symbol in seen:
            raise ValueError(f'11387 row {index}: invalid or duplicate security')
        seen.add(symbol)
        sid = 'TW:'+symbol
        values = row_values(row, index)
        if sid not in selection:
            continue
        stocks.append(dict(stock_id=sid, market='TW', ticker=symbol, name=name, provider=source['provider'],
                           raw_sha256=receipt['sha256'], row_number=index, source_column='代號', **origin))
        document_id = f'{SOURCE}:{symbol}:{trade_date}'
        documents.append(dict(document_id=document_id, external_id=document_id, doc_type='chip_report',
                              title=f'{name} {trade_date} 上櫃融資融券餘額',
                              content=f'{name} 的融資與融券交易取自櫃買中心彙總表。次一營業日來源備註：{row[-1].strip() or "空白"}。',
                              stock_ids=[sid], published_at=observed, available_at=observed,
                              availability_basis='observed_at_retrieval_not_original_publication', **origin))
        for column, value in values.items():
            metrics.append(dict(stock_id=sid, source_id=SOURCE, metric='tpex_margin_'+METRICS[column],
                                trade_date=trade_date, value=value, available_at=observed,
                                unit='percent' if column.endswith('使用率') else 'source_reported',
                                raw_sha256=receipt['sha256'], row_number=index, source_column=column))
    if {s['stock_id'] for s in stocks} != selection:
        raise ValueError('11387 incomplete coverage for selected stocks')
    provenance = dict(source_id=SOURCE, provider=source['provider'], url=source['dataset_url'],
                      license_type='OGDL-1.0', license_url=source['license_url'], attribution=source['attribution'],
                      usage=source['usage'], market='TPEX', independent_reference_status='needs-info',
                      quantity_scale='source_reported', scope='TPEx aggregate of securities finance companies and margin lenders')
    snapshot = dict(dataset_id=SOURCE, sha256=receipt['sha256'], bytes=receipt['bytes'],
                    retrieved_at=observed, resource_url=source['resource_url'])
    metadata = dict(adapter_version='tpex-margin-2', observed_at=observed, trade_date=trade_date,
                    raw_row_count=len(seen), source_snapshots=[snapshot])
    return dict(source_csv_b64=base64.b64encode(body).decode('ascii'), stocks=stocks, sources=[provenance], documents=documents, financial_metrics=[],
                chip_metrics=metrics, metadata=metadata)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--market', required=True, choices=('TPEX', 'TWSE'))
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--trade-date', required=True)
    parser.add_argument('--symbols', required=True, nargs='+')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    if args.market == 'TWSE':
        raise ValueError('11680 CSV is undated; the dated JSON is a separate representation')
    output = normalized_destination(args.output, args.manifest)
    payload = normalize(args.manifest, args.trade_date, validate_symbols(args.symbols))
    write_normalized(output, payload)
    print('Private margin import:', len(payload['stocks']), 'stocks,', len(payload['chip_metrics']), 'observations')


if __name__ == '__main__':
    main()
