"""Read one locally captured data.gov.tw 11633 receipt and its original CSV."""
import csv
import hashlib
import io
import json
import re
from datetime import date

from .calendar_archive import MIB, bounded_bytes
from .dates import timestamp
from .research import guarded

CATALOG = 'https://data.gov.tw/dataset/11633'
RESOURCE = 'https://www.tpex.org.tw/web/stock/exright/dailyquo/exDailyQ_result.php?l=zh-tw&o=data'
MARKERS = {'權', '息', '權息', '除權', '除息', '除權息'}
COLUMNS = ('除權息日期', '代號', '名稱', '除權息前收盤價', '除權息參考價', '權值', '息值',
           '權值加息值', '權或息', '漲停價', '跌停價', '開始交易基準價', '減除股利參考價',
           '現金股利', '每仟股無償配股', '現金增資股數', '現金增資認購價', '公開承銷股數',
           '員工認購股數', '原股東認購股數', '按持股比例仟股認購')


def _unique_fields(pairs):
    record = dict(pairs)
    if len(record) != len(pairs):
        raise ValueError('duplicate receipt field')
    return record


def read_capture(manifest, cutoff, selection):
    path = guarded(manifest)
    receipts = json.loads(bounded_bytes(path, MIB), object_pairs_hook=_unique_fields)
    if not isinstance(receipts, list) or not all(isinstance(entry, dict) for entry in receipts):
        raise ValueError('expected official resource manifest list')
    matches = [entry for entry in receipts if entry.get('id') == 11633]
    if len(matches) != 1:
        raise ValueError('expected one dataset 11633 receipt per manifest')
    entry = matches[0]
    observed = timestamp(entry['received_at'])
    if observed > cutoff:
        return None, []
    if (entry.get('catalog') != CATALOG or entry.get('url') != RESOURCE or entry.get('status') != '200'
            or type(entry.get('exit')) is not int or entry['exit'] != 0 or timestamp(entry['started_at']) > observed):
        raise ValueError('invalid 11633 acquisition receipt')
    body = bounded_bytes(guarded(path.parent/'11633.response'), 2 * MIB)
    digest = hashlib.sha256(body).hexdigest()
    if entry.get('sha256') != digest or type(entry.get('bytes')) is not int or entry['bytes'] != len(body):
        raise ValueError('11633 checksum or byte count mismatch')
    rows = csv.reader(io.StringIO(body.decode('utf-8-sig'), newline=''), strict=True)
    if next(rows, None) != list(COLUMNS):
        raise ValueError('unsupported 11633 CSV schema')
    actions, effective_dates = [], set()
    placeholders = identified = 0
    for number, row in enumerate(rows, 2):
        if len(row) != len(COLUMNS) or not re.fullmatch('[0-9]{8}', row[0]):
            raise ValueError('invalid 11633 row')
        day = date.fromisoformat(f'{row[0][:4]}-{row[0][4:6]}-{row[0][6:]}').isoformat()
        effective_dates.add(day)
        symbol, marker = row[1].strip(), row[8].strip()
        if not any(field.strip() for field in row[1:]):
            placeholders += 1
            continue
        if not re.fullmatch('[0-9A-Za-z]{4,12}', symbol) or marker not in MARKERS:
            raise ValueError('unidentified 11633 event')
        identified += 1
        if 'TW:'+symbol not in selection:
            continue
        actions.append({'type': 'ex_rights_dividend', 'market': 'TPEX', 'stock_id': 'TW:'+symbol,
                        'effective_date': day, 'marker': marker, 'row_number': number,
                        'raw_sha256': digest, 'observed_at': entry['received_at']})
    source = {'dataset_url': CATALOG, 'resource_url': RESOURCE, 'license': 'OGDL-1.0',
              'attribution': '金融監督管理委員會證券期貨局／櫃買中心 上櫃股票除權除息計算結果表',
              'market': 'TPEX', 'raw_sha256': digest, 'observed_at': entry['received_at'],
              'row_dates': sorted(effective_dates), 'identified_event_rows': identified,
              'date_only_rows': placeholders, 'coverage': 'positive_rows_only'}
    return source, actions
