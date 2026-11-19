"""Explicit notices that change a named version of one normalized record."""
from __future__ import annotations

import re

from .dates import timestamp

KEY_FIELDS = {
    'documents': ('document_id',),
    'financial_metrics': ('stock_id', 'metric', 'period_end', 'period_type'),
    'chip_metrics': ('stock_id', 'metric', 'trade_date'),
}
FIELDS = {'schema_version', 'action', 'group', 'key', 'source_id', 'target_snapshot_sha256',
          'effective_at', 'published_at', 'source_reference', 'evidence'}


def record_key(group, row):
    return tuple(row[field] for field in KEY_FIELDS[group])


def validate_notice(notice):
    if not isinstance(notice, dict) or set(notice) != FIELDS or notice['schema_version'] != 'source-revision-1':
        raise ValueError('invalid source revision notice')
    group, key = notice['group'], notice['key']
    if not isinstance(group, str) or group not in KEY_FIELDS:
        raise ValueError('unsupported source revision group')
    if (not isinstance(key, dict) or set(key) != set(KEY_FIELDS[group])
            or not all(isinstance(v, str) and v.strip() for v in key.values())):
        raise ValueError('invalid source revision logical key')
    if notice['action'] not in ('withdraw', 'correct', 'republish'):
        raise ValueError('unknown source revision action')
    if not isinstance(notice['target_snapshot_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', notice['target_snapshot_sha256']):
        raise ValueError('invalid source revision target snapshot')
    for field in ('source_id', 'source_reference', 'evidence'):
        if not isinstance(notice[field], str) or not 0 < len(notice[field].strip()) <= 8192:
            raise ValueError('source revision requires bounded ' + field)
    timestamp(notice['effective_at'])
    timestamp(notice['published_at'])


def validate_envelope(payload):
    notice = payload['source_revision']
    validate_notice(notice)
    if [row['source_id'] for row in payload.get('sources', [])] != [notice['source_id']]:
        raise ValueError('unknown or ambiguous revision source')
    observed = timestamp(payload['metadata']['observed_at'])
    if timestamp(notice['published_at']) > observed:
        raise ValueError('revision publication is later than observation')
    group = notice['group']
    for name in KEY_FIELDS:
        rows = payload.get(name, [])
        if len(rows) != int(name == group and notice['action'] != 'withdraw'):
            raise ValueError('revision envelope must contain only its declared replacement')
    if notice['action'] != 'withdraw':
        row = payload[group][0]
        if row['source_id'] != notice['source_id'] or record_key(group, row) != record_key(group, notice['key']):
            raise ValueError('revision replacement differs from target identity')
        if timestamp(row.get('available_at', row.get('published_at'))) < max(
                timestamp(notice['published_at']), timestamp(notice['effective_at'])):
            raise ValueError('replacement availability precedes revision effective time or publication')


class RevisionTarget:
    """Find the current version of one logical record during the bounded ledger scan."""

    def __init__(self, payload):
        self.notice = payload['source_revision']
        self.source = payload['sources'][0]
        self.group = self.notice['group']
        self.key = record_key(self.group, self.notice['key'])
        self.stock_ids = {row['stock_id'] for row in payload['stocks']}
        self.observed = timestamp(payload['metadata']['observed_at'])
        self.latest_notice = None
        self.latest_observed = None
        self.latest_activation = None
        self.activation = activation(payload)
        self.latest_record = None
        self.rank = None
        self.target_scope = None
        self.version = None
        if self.notice['action'] != 'withdraw' and self.scope(payload[self.group][0]) != self.stock_ids:
            raise ValueError('revision replacement stock coverage differs from envelope')

    def scope(self, record):
        return set(record['stock_ids']) if self.group == 'documents' else {record['stock_id']}

    def inspect(self, sha, observed, prior, now):
        if sha == self.notice['target_snapshot_sha256'] and not any(
                source.get('source_id') == self.source['source_id']
                and source.get('provider') == self.source['provider']
                and source.get('url') == self.source.get('url') for source in prior.get('sources', [])):
            raise ValueError('source revision origin differs from target source')
        prior_notice = prior.get('source_revision')
        if prior_notice:
            if prior_notice['group'] == self.group and prior_notice['key'] == self.notice['key']:
                if prior_notice['source_id'] != self.notice['source_id']:
                    raise ValueError('conflicting revision source')
                # The scan is ordered by observation and registration. Admission
                # requires successive notices to have increasing source publication.
                if self.latest_notice and timestamp(prior_notice['published_at']) < timestamp(self.latest_notice['published_at']):
                    return
                self.latest_notice = prior_notice
                self.latest_observed = timestamp(observed)
                self.latest_activation = activation(prior)
                self.version = sha
                self.target_scope = {stock['stock_id'] for stock in prior['stocks']}
            return
        for record in prior.get(self.group, []):
            if record_key(self.group, record) != self.key:
                continue
            if record['source_id'] != self.notice['source_id']:
                raise ValueError('revision target source mismatch')
            available = timestamp(record.get('available_at', record.get('published_at')))
            if self.latest_notice or available > now:
                continue
            rank = timestamp(observed), available
            if self.rank == rank and self.latest_record != record:
                raise ValueError('conflicting same-time revision target')
            if self.rank is None or rank > self.rank:
                self.rank, self.latest_record = rank, record
                self.version, self.target_scope = sha, self.scope(record)

    def verify(self):
        if self.version != self.notice['target_snapshot_sha256'] or self.target_scope != self.stock_ids:
            raise ValueError('unknown, stale or conflicting revision target or stock coverage')
        withdrawn = self.latest_notice and self.latest_notice['action'] == 'withdraw'
        if bool(withdrawn) != (self.notice['action'] == 'republish'):
            raise ValueError('invalid revision action for target state')
        if self.rank and self.observed < self.rank[0]:
            raise ValueError('revision observation precedes target')
        if self.latest_notice:
            if (timestamp(self.notice['published_at']) <= timestamp(self.latest_notice['published_at'])
                    or self.observed < self.latest_observed or self.activation < self.latest_activation):
                raise ValueError('conflicting or out-of-order revision publication')


def activation(payload):
    notice = payload['source_revision']
    times = [timestamp(notice['effective_at']), timestamp(payload['metadata']['observed_at'])]
    if notice['action'] != 'withdraw':
        row = payload[notice['group']][0]
        times.append(timestamp(row.get('available_at', row.get('published_at'))))
    return max(times)


def revision_entry(snapshot, stock_ids):
    payload = snapshot['revision_payload']
    return {'notice': payload['source_revision'], 'snapshot_sha256': snapshot['sha256'],
            'stock_ids': sorted({row['stock_id'] for row in payload['stocks']} & set(stock_ids)),
            'observed_at': snapshot['observed_at'], 'recorded_at': snapshot['recorded_at']}


def audit_revisions(snapshots, entries, facts, stock_ids, cutoff):
    import hashlib
    from .research_history import canonical, validate_payload

    by_sha = {snapshot['sha256']: snapshot for snapshot in snapshots}
    notices = [snapshot for snapshot in snapshots if 'revision_payload' in snapshot]
    expected, heads, visible = [], {}, {}
    for snapshot in sorted(notices, key=lambda item: timestamp(item['revision_payload']['source_revision']['published_at'])):
        payload = snapshot['revision_payload']
        if (hashlib.sha256(canonical(payload)).hexdigest() != snapshot['sha256']
                or validate_payload(payload)['observed_at'] != snapshot['observed_at']
                or payload['sources'] != snapshot['sources'] or payload['metadata'] != snapshot['metadata']):
            raise ValueError('source revision archived envelope mismatch')
        notice = payload['source_revision']
        previous = by_sha.get(notice['target_snapshot_sha256'])
        source = payload['sources'][0]
        if (not previous or not any(all(row.get(k) == source.get(k) for k in ('source_id', 'provider', 'url'))
                                    for row in previous['sources'])
                or timestamp(previous['recorded_at']) > timestamp(snapshot['recorded_at'])
                or timestamp(previous['observed_at']) > timestamp(snapshot['observed_at'])):
            raise ValueError('unresolved source revision parent')
        group = notice['group']
        key = (group, source['source_id'], record_key(group, notice['key']))
        prior = heads.get(key)
        if ((prior and prior['sha256'] != previous['sha256'])
                or ('revision_payload' in previous and not prior)):
            raise ValueError('conflicting source revision branch')
        withdrawn = bool(prior and prior['revision_payload']['source_revision']['action'] == 'withdraw')
        if withdrawn != (notice['action'] == 'republish'):
            raise ValueError('invalid archived revision transition')
        if prior:
            prior_payload = prior['revision_payload']
            if (timestamp(prior_payload['source_revision']['published_at']) >= timestamp(notice['published_at'])
                    or activation(prior_payload) > activation(payload)):
                raise ValueError('out-of-order archived revision transition')
        heads[key] = snapshot
        if activation(payload) <= cutoff:
            expected.append(revision_entry(snapshot, stock_ids))
            visible[key] = snapshot
    if expected != entries or any(not entry['stock_ids'] for entry in expected):
        raise ValueError('source revision replay evidence mismatch')

    if not visible:
        return
    kinds = {'financial_metric': 'financial_metrics', 'chip_metric': 'chip_metrics'}
    numeric = {(kinds[f['kind']], f['source_id'], record_key(kinds[f['kind']], f)): f
               for f in facts if f['kind'] in kinds}
    for key, snapshot in visible.items():
        group = key[0]
        if group == 'documents':
            continue
        fact = numeric.get(key)
        payload = snapshot['revision_payload']
        if payload['source_revision']['action'] == 'withdraw':
            if fact:
                raise ValueError('withdrawn source revision still present in facts')
        else:
            from .financial_definitions import financial_definition
            row = financial_definition(payload[group][0])
            fields = ('value', 'unit', 'currency', 'normalization_version', 'statement_scope', 'report_basis')
            if (not fact or fact['input_snapshot_sha256'] != snapshot['sha256']
                    or fact['source_available_at'] != row['available_at']
                    or any(fact.get(k) != row.get(k) for k in fields)):
                raise ValueError('source revision replacement differs from facts')
