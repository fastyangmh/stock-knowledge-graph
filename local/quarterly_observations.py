"""Identities of source observations in existing quarterly normalized snapshots."""
from . import quarterly_balance, quarterly_income
from .dates import timestamp

MOPS = {f'mops_{dataset}': spec for dataset, spec in
        {**quarterly_balance.SOURCES, **quarterly_income.SOURCES}.items()}


def quarterly_receipt(payload):
    """Return the identity and checksum of the evidence observed at one time."""
    if 'source_revision' in payload:
        return None
    metadata = payload['metadata']
    if metadata.get('adapter_version') == 'mops-quarterly-v1':
        receipt, = metadata['source_snapshots']
        observed = timestamp(metadata['observed_at'])
        if (timestamp(receipt['retrieved_at']) != observed or
                [s['source_id'] for s in payload['sources']] != [receipt['dataset_id']]):
            raise ValueError('quarterly receipt time or source differs from observation')
        return (receipt['dataset_id'], observed), receipt['sha256']
    if metadata.get('adapter_version') == 'issuer-cashflow-notes-v1':
        source, = payload['sources']
        return (source['source_id'], timestamp(metadata['observed_at'])), metadata['note_sha256']
    return None


def missing_cells(payload):
    """Read explicit source markers, including those written by the first v1 adapters."""
    metadata = payload['metadata']
    adapter = metadata.get('adapter_version')
    if 'source_revision' in payload or adapter not in ('mops-quarterly-v1', 'issuer-cashflow-notes-v1'):
        return
    source, = payload['sources']
    sid = source['source_id']
    for cell in metadata.get('missing_values', []):
        if cell['raw_value'].strip() not in ('', '-', '--', 'N/A'):
            raise ValueError('expected explicit missing quarterly source marker')
        if adapter == 'mops-quarterly-v1':
            metric, _ = MOPS[sid][-1][cell['source_field']]
            stock_id, end = cell['stock_id'], cell['period_end']
        else:
            document, = payload['documents']
            stock_id, = document['stock_ids']
            end, metric = document['period_end'], cell['metric']
        yield dict(source_id=sid, stock_id=stock_id, period_end=end, period_type='quarter',
                   metric=metric, available_at=metadata['observed_at'])
