"""Stock-independent news metadata reviewed for inclusion in private research reports."""
import hashlib

from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .dates import iso_date, timestamp

NEWS = {11546: 'twse_news_11546', 6040: 'fsc_news_6040'}
VERSION = 'official-news-index-v1'


def official_link(value, host):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 or c == '\\' for c in value):
        raise ValueError('invalid official article URL')
    url = urlsplit(value)
    if url.scheme != 'https' or url.netloc != host or not url.path.startswith('/'):
        raise ValueError('unreviewed article host or protocol')


def validate_articles(source_id, articles, observed):
    if source_id not in NEWS.values() or not isinstance(articles, list) or not articles:
        raise ValueError('invalid news index')
    seen = set()
    is_rss = source_id == NEWS[6040]
    host = 'www.fsc.gov.tw' if is_rss else 'www.twse.com.tw'
    for position, entry in enumerate(articles, 1 if is_rss else 2):
        fields = {'external_id', 'title', 'link', 'row_number'}
        fields.update(('published_at', 'has_description') if is_rss else ('published_date',))
        if not isinstance(entry, dict) or entry.keys() != fields or entry['row_number'] != position:
            raise ValueError(f'article {position}: unexpected index fields')
        key, title = entry['external_id'], entry['title']
        if not isinstance(key, str) or not key or key in seen or not isinstance(title, str) or not title.strip():
            raise ValueError(f'article {position}: empty title/identity or duplicate identity')
        seen.add(key)
        official_link(entry['link'], host)
        if is_rss:
            official_link(key, host)
            if type(entry['has_description']) is not bool or timestamp(entry['published_at']) > observed:
                raise ValueError(f'article {position}: invalid RSS description or publication time')
        elif key != entry['link'] or iso_date(entry['published_date']) > observed.astimezone(ZoneInfo('Asia/Taipei')).date():
            raise ValueError(f'article {position}: invalid link identity or publication date')


def validate_news_payload(payload):
    metadata = payload.get('metadata', {})
    if not isinstance(metadata, dict) or metadata.get('adapter_version') != VERSION:
        if 'articles' in payload:
            raise ValueError('articles require a reviewed news index')
        return False
    if any(payload.get(group) for group in ('stocks', 'documents', 'financial_metrics', 'chip_metrics', 'source_revision')):
        raise ValueError('news index has no source-supported stock links or derived documents')
    source, = payload['sources']
    snapshot, = metadata['source_snapshots']
    if (source['source_id'] != snapshot['dataset_id'] or metadata['observed_at'] != snapshot['retrieved_at']
            or metadata['raw_row_count'] != len(payload['articles'])):
        raise ValueError('news index receipt does not match rows')
    validate_articles(source['source_id'], payload['articles'], timestamp(metadata['observed_at']))
    return True


def evidence_source(payload):
    metadata = payload.get('metadata', {})
    if metadata.get('adapter_version') in (VERSION, 'official-industry-v1'):
        source, = payload['sources']
        return source['source_id']
    return None


def audit_indexes(quality, cutoff):
    """Verify the latest full feed visible at the cutoff against its ledger hash."""
    from .research_history import canonical

    latest = {}
    for saved in quality.get('snapshots', []):
        meta = saved.get('metadata', {})
        if meta.get('adapter_version') != VERSION:
            continue
        source, = saved['sources']
        sid = source['source_id']
        observed = timestamp(saved['observed_at'])
        if not observed == timestamp(meta['observed_at']) <= timestamp(saved['recorded_at']) <= cutoff:
            raise ValueError('invalid news receipt times')
        if sid not in latest or timestamp(latest[sid]['observed_at']) < observed:
            latest[sid] = saved
        elif timestamp(latest[sid]['observed_at']) == observed:
            raise ValueError('ambiguous news receipt')
    indexes = quality.get('news_indexes', [])
    if not isinstance(indexes, list) or [entry['source_id'] for entry in indexes] != sorted(latest):
        raise ValueError('missing or unexpected news index')
    for entry in indexes:
        saved = latest[entry['source_id']]
        meta = saved['metadata']
        receipt, = meta['source_snapshots']
        payload = dict(stocks=[], documents=[], sources=saved['sources'], financial_metrics=[], chip_metrics=[],
                       metadata=meta, articles=entry['articles'])
        validate_news_payload(payload)
        if (entry['raw_sha256'] != receipt['sha256'] or entry['snapshot_sha256'] != saved['sha256']
                or hashlib.sha256(canonical(payload)).hexdigest() != saved['sha256']):
            raise ValueError('news index checksum mismatch')
