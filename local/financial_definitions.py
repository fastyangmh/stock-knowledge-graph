"""Canonical financial definition aliases, without inferring missing values."""
from __future__ import annotations

DEFINITION_KEYS = ('normalization_version', 'statement_scope', 'report_basis', 'currency')


def unverified_definition(value):
    return not isinstance(value, str) or value.strip().lower() in (
        '', 'source_reported', 'unknown', 'unspecified', 'n/a')

def financial_definition(row):
    result = dict(row)
    for first, alias in (('statement_scope', 'consolidation'), ('report_basis', 'value_basis')):
        a, b = row.get(first), row.get(alias)
        if a is not None and b is not None and a != b:
            raise ValueError('conflicting financial definition: '+first+'/'+alias)
        result[first] = result[alias] = a if a is not None else b
    return result


def validate_financial_versions(payload):
    metadata = payload['metadata']
    adapter = metadata.get('adapter_version')
    for row in payload.get('financial_metrics', []):
        version = row.get('normalization_version')
        if adapter in ('mops-quarterly-v1', 'issuer-cashflow-notes-v1') and version != adapter:
            raise ValueError('quarterly normalization version differs from source adapter')
        if (row['source_id'] in ('twse_monthly_revenue', 'tpex_monthly_revenue') and version is not None
                and version != metadata.get('normalization_version')):
            raise ValueError('monthly normalization version differs from source unit policy')


def source_definitions(payload):
    """Read per-source contracts from immutable single-adapter v1 inputs.

    Both official markets use the same reviewed monthly unit policy. Other
    datasets may coexist, but an existing source cannot switch definitions.
    """
    metadata = payload['metadata']
    version = metadata.get('normalization_version')
    adapter = metadata.get('adapter_version')
    definitions = {}
    for source in payload.get('sources', []):
        sid = source['source_id']
        definitions[('normalization', sid)] = version
        # Notices name an immutable target. Legacy notices carry its unit
        # policy but are not produced by the target's source adapter.
        if 'source_revision' not in payload:
            # Chip v2 adds the original bytes to the same unit and column contract.
            definitions[('adapter', sid)] = {'tpex-margin-2': 'tpex-margin-1',
                                             'tpex-institutional-2': 'tpex-institutional-1'}.get(adapter, adapter)
        if sid in ('twse_monthly_revenue', 'tpex_monthly_revenue'):
            definitions[('family', 'official_monthly_revenue')] = version
    return definitions
