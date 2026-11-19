"""Read original bytes paired with a local receipt for one offline-reviewed dataset."""
import hashlib
import json
from pathlib import Path

from .calendar_archive import MIB, bounded_bytes
from .core import ROOT
from .dates import analysis_cutoff, timestamp
from .research import guarded


def _unique(fields):
    result = dict(fields)
    if len(result) != len(fields):
        raise ValueError('duplicate receipt field')
    return result


def read_receipt(manifest: Path, source_id: str, catalog_id: int):
    entries = json.loads((ROOT/'local/official_datasets.json').read_text(encoding='utf-8'))
    sources = [item for item in entries if item['dataset_id'] == source_id]
    if len(sources) != 1:
        raise ValueError('unknown offline dataset')
    source = sources[0]
    if (source.get('enabled') is not False or source.get('usage') != 'offline_saved_receipt_only'
            or source.get('license_reviewed') is not True
            or source.get('dataset_url') != f'https://data.gov.tw/dataset/{catalog_id}'):
        raise ValueError('dataset lacks offline review')
    path = guarded(manifest)
    entries = json.loads(bounded_bytes(path, MIB), object_pairs_hook=_unique)
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise ValueError('expected a list of official resource receipts')
    matches = [item for item in entries if type(item.get('id')) is int and item['id'] == catalog_id]
    if len(matches) != 1:
        raise ValueError(f'expected one receipt for {catalog_id}')
    entry = matches[0]
    mime = entry.get('mime')
    types = {'csv': {'application/csv', 'text/csv'}, 'rss': {'text/xml', 'application/xml', 'application/rss+xml'}}
    fmt = source['format']
    if not isinstance(mime, str) or mime.partition(';')[0].strip().lower() not in types.get(fmt, set()):
        raise ValueError(f'expected {fmt.upper()} MIME type for {catalog_id}')
    if (entry.get('catalog') != source['dataset_url'] or entry.get('url') != source['resource_url']
            or entry.get('status') != '200' or type(entry.get('exit')) is not int
            or entry['exit'] != 0 or entry.get('error') != ''
            or timestamp(entry.get('started_at')) > analysis_cutoff(entry.get('received_at'))):
        raise ValueError(f'invalid acquisition receipt for {catalog_id}')
    body = bounded_bytes(guarded(path.parent/f'{catalog_id}.response'), 16 * MIB)
    if (type(entry.get('bytes')) is not int or len(body) != entry['bytes']
            or hashlib.sha256(body).hexdigest() != entry.get('sha256')):
        raise ValueError(f'{catalog_id} checksum or byte count mismatch')
    return source, entry, body
