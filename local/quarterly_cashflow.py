"""Import a hash-bound, private transcription of reviewed issuer cash-flow statements."""
import argparse
import hashlib
import re
from pathlib import Path
from zoneinfo import ZoneInfo

from .dates import timestamp
from .official_adapter import number
from .quarterly_import import read_bytes, write_normalized
from .research import guarded
from .research_history import strict_json

VERSION = 'issuer-cashflow-notes-v1'
METRICS = ('operating_cash_flow', 'investing_cash_flow', 'financing_cash_flow',
           'opening_cash_equivalents', 'closing_cash_equivalents', 'net_change_cash_equivalents')

# Both editions show consolidated January–September amounts in thousands of TWD.
# Add a filing only after checking its period, scope, units, editions and usage terms.
TSMC = 'https://investor.tsmc.com/sites/ir/financial-report/2026/TSMC%202026Q3%20Consolidated%20Financial%20Statements_'
GLOBALWAFERS = ('https://www.sas-globalwafers.com/wp-content/uploads/2025/11/'
                'GlobalWafers_2025Q3-consolidated-financial-statement_')
FILINGS = {
    ('2330', '2026-09-30'): ('台灣積體電路製造股份有限公司', 'TWSE', TSMC+'C.pdf', TSMC+'E.pdf',
                             'https://www.tsmc.com/english/legal_and_trademark', '2026-11-10'),
    ('6488', '2025-09-30'): ('環球晶圓股份有限公司', 'TPEx', GLOBALWAFERS+'CN.pdf', GLOBALWAFERS+'EN.pdf',
                             'https://www.sas-globalwafers.com/en/investor/financial-information_en/', '2025-11-04'),
}


def amount(raw):
    if not isinstance(raw, str) or not 0 < len(raw) <= 32:
        raise ValueError('expected reported amount or missing marker')
    text = raw.strip()
    if re.fullmatch(r'\([0-9][0-9,]*\)', text):
        text = '-' + text[1:-1]
    if text not in ('--', '-', 'N/A') and not re.fullmatch(r'[+-]?[0-9][0-9,]*', text):
        raise ValueError('unexpected cash-flow integer or missing marker')
    value = number(text)
    if value is not None and (type(value) is not int or abs(value) >= 2 ** 53):
        raise ValueError('expected exact integer thousands of TWD')
    return value


def normalize(body, checksum):
    if hashlib.sha256(body).hexdigest() != checksum:
        raise ValueError('cash-flow note checksum mismatch')
    notes = strict_json(body)
    header = {'schema_version', 'symbol', 'period_end', 'observed_at', 'editions'}
    if set(notes) != header or notes['schema_version'] != VERSION:
        raise ValueError('unexpected cash-flow note schema')
    symbol, end = notes['symbol'], notes['period_end']
    if not isinstance(symbol, str) or not isinstance(end, str):
        raise ValueError('invalid issuer or reporting period')
    filing = FILINGS.get((symbol, end))
    if filing is None:
        raise ValueError('unreviewed issuer or reporting period')
    issuer, market, primary_url, translation_url, rights_url, approval_date = filing
    observed = timestamp(notes['observed_at'])
    if observed.astimezone(ZoneInfo('Asia/Taipei')).date().isoformat() < approval_date:
        raise ValueError('note predates the published filing')
    time = observed.isoformat()
    start = end[:4] + '-01-01'
    stock = 'TW:' + symbol
    sid = 'issuer_cashflow_notes_' + symbol
    source = dict(provider=issuer, source_id=sid, market=market, sector='general', statement='cashflow',
                  url=primary_url, reference_url=translation_url, license_url=rights_url,
                  license_type='issuer_reserved_rights_private_viewing_notes',
                  attribution=issuer, evidence_type='manual_transcription',
                  cross_check='same_issuer_translation', official_bytes_archived=False)
    rows = []
    missing = []
    editions = notes['editions']
    if not isinstance(editions, list) or len(editions) != 2:
        raise ValueError('expected primary and translation notes')
    context = dict(period_start=start, period_end=end, unit='TWD_thousands',
                   statement_scope='consolidated', report_basis='cumulative')
    for edition, url in zip(editions, (primary_url, translation_url), strict=True):
        if (not isinstance(edition, dict) or set(edition) != {'url', 'context', 'cells'}
                or edition['url'] != url or edition['context'] != context
                or not isinstance(edition['cells'], dict) or set(edition['cells']) != set(METRICS)):
            raise ValueError('unexpected edition or cash-flow fields')
        for metric, cell in edition['cells'].items():
            if (not isinstance(cell, dict) or set(cell) != {'locator', 'raw_value'}
                    or not isinstance(cell['locator'], str) or not 1 <= len(cell['locator'].strip()) <= 256):
                raise ValueError(f'{metric}: expected a cell value and report locator')

    balance_dates = {'opening_cash_equivalents': start, 'closing_cash_equivalents': end}
    for metric in METRICS:
        primary, check = [edition['cells'][metric] for edition in editions]
        value = amount(primary['raw_value'])
        if value != amount(check['raw_value']):
            raise ValueError(f'{metric}: cash-flow transcriptions disagree')
        evidence = dict(metric=metric, raw_value=primary['raw_value'], locator=primary['locator'],
                        reference_value=check['raw_value'], reference_locator=check['locator'])
        if value is None:
            missing.append(evidence)
            continue
        instant = balance_dates.get(metric)
        rows.append(dict(**evidence, value=value, note_sha256=checksum, source_id=sid, stock_id=stock,
                         unit='TWD_thousands', currency='TWD', statement_scope='consolidated',
                         normalization_version=VERSION, period_start=start, period_end=end,
                         period_type='quarter', report_basis='point_in_time' if instant else 'cumulative',
                         instant_date=instant, available_at=time))

    if not rows:
        raise ValueError('no numeric cash-flow observation')
    doc_id = f'{sid}:{end}'
    title = f'{issuer} {end} 合併現金流量表核對筆記'
    document = dict(document_id=doc_id, external_id=doc_id, source_id=sid, source_url=primary_url,
                    license_url=rights_url, attribution=issuer, title=title, content=title,
                    doc_type='financial', stock_ids=[stock], period_end=end, published_at=time,
                    available_at=time, availability_basis='observed_at_manual_review',
                    board_approval_date=approval_date)
    return dict(stocks=[dict(stock_id=stock, ticker=symbol, market='TW', name=issuer)],
                documents=[document], sources=[source], chip_metrics=[], financial_metrics=rows,
                metadata=dict(adapter_version=VERSION, observed_at=time, missing_values=missing,
                              note_sha256=checksum, evidence_type='manual_transcription',
                              research_selection=dict(mode='explicit_symbols_not_index_membership', stock_ids=[stock])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notes', required=True, type=Path)
    parser.add_argument('--sha256', required=True, help='Expected SHA256 of the private review notes')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    payload = normalize(read_bytes(guarded(args.notes), 128 * 1024), args.sha256)
    write_normalized(payload, guarded(args.output))


if __name__ == '__main__':
    main()
