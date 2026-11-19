"""Normalize an archived official news index or quarterly company classification."""
import argparse
import csv
import io
import re
from email.utils import format_datetime, parsedate_to_datetime
from xml.etree import ElementTree
from pathlib import Path
from zoneinfo import ZoneInfo

from .collect_official import atomic_bytes
from .dates import timestamp
from .offline_receipt import read_receipt
from .news_index import NEWS, VERSION
from .official_adapter import report_date
from .quarterly_import import period_end
from .research import guarded
from .research_history import canonical, validate_payload
from .safety import exclusive_lock

INDUSTRIES = {20756: 'TWSE', 20757: 'TPEx'}
INDUSTRY_FIELDS = ('出表日期 年度 季別 公司代號 公司名稱 產業別 基本每股盈餘(元) 普通股每股面額 '
                   '營業收入 營業利益 營業外收入及支出 稅後淨利').split()


def csv_records(body, fields):
    reader = csv.reader(io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
    if next(reader, None) != fields:
        raise ValueError('unsupported CSV header')
    for index, cells in enumerate(reader, 2):
        if len(fields) != len(cells):
            raise ValueError(f'row {index}: unexpected CSV width')
        yield index, dict(zip(fields, (cell.strip() for cell in cells)))


def roc_date(value):
    if not re.fullmatch(r'[0-9]{7}', value):
        raise ValueError('expected ROC YYYMMDD date')
    return report_date(value)


def industry(payload, source, receipt, body, market):
    observed = receipt['received_at']
    today = timestamp(observed).astimezone(ZoneInfo('Asia/Taipei')).date()
    dates, symbols = set(), set()
    for index, row in csv_records(body, INDUSTRY_FIELDS):
        symbol, name, sector = row['公司代號'], row['公司名稱'], row['產業別']
        end, report = period_end(row), roc_date(row['出表日期'])
        if not end <= report <= today:
            raise ValueError(f'row {index}: period/report/receipt dates inconsistent')
        dates.add((end, report))
        if (len(dates) != 1 or not re.fullmatch('[0-9]{4}', symbol) or symbol in symbols
                or {name, sector} & {'', '-', '--', 'N/A'}):
            raise ValueError(f'row {index}: mixed period, missing or duplicate industry identity')
        symbols.add(symbol)
        sid = 'TW:'+symbol
        did = f'{source["source_id"]}:{symbol}:{end.isoformat()}'
        payload['stocks'].append(dict(stock_id=sid, market='TW', ticker=symbol, name=name))
        payload['documents'].append(dict(
            document_id=did, external_id=did, doc_type='industry_report', title=f'{name} {end} 產業別',
            content=f'{market}，{end} 季表，公司代號 {symbol}，來源列示產業別為「{sector}」。',
            stock_ids=[sid], published_at=observed, available_at=observed,
            availability_basis='observed_at_retrieval_not_original_publication', period_end=end.isoformat(),
            source_report_date=report.isoformat(), industry=sector, relation_basis='source_reported_industry',
            raw_sha256=receipt['sha256'], row_number=index, source_column='產業別',
            source_id=source['source_id'], source_url=source['url'], attribution=source['attribution'],
            license_url=source['license_url']))
    if not symbols:
        raise ValueError('empty industry dataset')
    payload['metadata']['raw_row_count'] = len(symbols)


def rss_articles(body):
    xml = body.decode('utf-8-sig')
    if '<!DOCTYPE' in xml or '<!ENTITY' in xml:
        raise ValueError('RSS document type/entity declarations are unsupported')
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ValueError(f'invalid RSS XML at {exc.position}') from exc
    if root.tag != 'rss' or root.attrib != {'version': '2.0'} or [e.tag for e in root] != ['channel']:
        raise ValueError('expected RSS 2.0 channel')
    channel = root[0]
    if (any(e.tag not in {'title', 'link', 'description', 'language', 'category', 'item'} for e in channel)
            or any(len(channel.findall(tag)) != 1 for tag in ('title', 'link', 'description'))):
        raise ValueError('unexpected RSS channel schema')
    articles = []
    for index, item in enumerate(channel.findall('item'), 1):
        tags = [field.tag for field in item]
        if (any(tag not in {'title', 'link', 'guid', 'pubDate', 'description', 'category'} for tag in tags)
                or any(tags.count(tag) != 1 for tag in ('title', 'link', 'guid', 'pubDate'))
                or tags.count('description') > 1 or any(len(field) for field in item)
                or item.find('guid').get('isPermaLink') != 'true'):
            raise ValueError(f'item {index}: unsupported RSS item schema')
        published = parsedate_to_datetime(item.findtext('pubDate'))
        if published.tzinfo is None or format_datetime(published, usegmt=True) != item.findtext('pubDate'):
            raise ValueError(f'item {index}: expected reviewed GMT date')
        articles.append(dict(external_id=item.findtext('guid'), title=item.findtext('title'),
                             link=item.findtext('link'), published_at=published.isoformat(),
                             row_number=index, has_description=bool(item.findtext('description'))))
    return articles


def normalize(manifest, dataset):
    source_id = NEWS.get(dataset, f'mops_industry_{dataset}')
    registered, receipt, body = read_receipt(manifest, source_id, dataset)
    source = dict(source_id=registered['dataset_id'], provider=registered['provider'], url=registered['dataset_url'],
                  attribution=registered['attribution'], license_url=registered['license_url'],
                  license_type='OGDL-1.0', usage=registered['usage'], permitted_use=registered['permitted_use'])
    snapshot = dict(dataset_id=source['source_id'], resource_url=registered['resource_url'],
                    bytes=receipt['bytes'], sha256=receipt['sha256'], retrieved_at=receipt['received_at'])
    payload = dict(stocks=[], sources=[source], documents=[], financial_metrics=[], chip_metrics=[],
                   metadata=dict(adapter_version='official-industry-v1', observed_at=receipt['received_at'],
                                 source_snapshots=[snapshot]))
    if dataset in INDUSTRIES:
        source['market'] = INDUSTRIES[dataset]
        industry(payload, source, receipt, body, source['market'])
    else:
        if dataset == 11546:
            articles = [dict(title=row['標題'], link=row['連結'], external_id=row['連結'],
                             published_date=roc_date(row['日期']).isoformat(), row_number=index)
                        for index, row in csv_records(body, ['標題', '連結', '日期'])]
        else:
            articles = rss_articles(body)
        payload['articles'] = articles
        payload['metadata'].update(adapter_version=VERSION, raw_row_count=len(articles))
    validate_payload(payload)
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', required=True, type=int, choices=sorted(set(INDUSTRIES) | NEWS.keys()))
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    output, manifest = guarded(args.output), guarded(args.manifest)
    if output.is_relative_to(manifest.parent):
        raise ValueError('save normalized output outside the capture directory')
    payload = normalize(manifest, args.dataset)
    data = canonical(payload)
    with exclusive_lock(output):
        if output.exists():
            if output.stat().st_size != len(data) or output.read_bytes() != data:
                raise ValueError('changed capture requires a new output path')
        else:
            atomic_bytes(output, data)
    print(f'{args.dataset}: {payload["metadata"]["raw_row_count"]} rows')


if __name__ == '__main__':
    main()
