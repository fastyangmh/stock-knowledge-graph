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
