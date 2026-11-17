"""Opt-in, evidence-bound monthly unit conversion; legacy inputs stay unchanged.

The evidence manifest is a review assertion, not automatic provider truth. Its
bytes and the referenced documents must be retained privately for review.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path
import re
from urllib.parse import urlsplit

from .financial_definitions import financial_definition
from .research_history import strict_json
from .safety import private_path

VERSION = 'official-monthly-twd-v1'
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024


def apply_unit_evidence(payload, evidence_path):
    path = private_path(evidence_path)
    with path.open('rb') as stream:
        body = stream.read(MAX_EVIDENCE_BYTES+1)
    evidence = strict_json(body)
    if evidence.get('schema_version') != 'financial-unit-evidence-1.0' or evidence.get('normalization_version') != VERSION:
        raise ValueError('unsupported financial unit evidence version')
    decisions = evidence.get('decisions')
    if not isinstance(decisions, list) or not 1 <= len(decisions) <= 1000:
        raise ValueError('invalid financial unit evidence decisions')
    snapshots = {s['dataset_id']: s['sha256'] for s in payload['metadata']['source_snapshots']}
    rows = {(r['source_id'], r['stock_id'], r['period_end']) for r in payload['financial_metrics']}
    verified, read_bytes = {}, len(body)
    for decision in decisions:
        d = financial_definition(decision)
        key = tuple(d.get(k) for k in ('source_id','stock_id','period_end'))
        if key in verified or key not in rows:
            raise ValueError('duplicate or unused financial unit decision')
        if d['source_id'] not in ('twse_monthly_revenue','tpex_monthly_revenue') or d.get('raw_snapshot_sha256') != snapshots.get(d['source_id']):
            raise ValueError('financial unit raw snapshot mismatch')
        if (d.get('raw_unit') != 'TWD_thousands' or d.get('currency') != 'TWD' or
                d.get('statement_scope') not in ('consolidated','separate') or d.get('report_basis') != 'single_period'):
            raise ValueError('unsupported financial unit definition')
        references = d.get('references')
        if not isinstance(references, list) or not 1 <= len(references) <= 10:
            raise ValueError('financial unit decision requires reference evidence')
        for reference in references:
            relative = Path(reference['path'])
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('unsafe financial evidence path')
            target = private_path(path.parent/relative)
            if not target.is_relative_to(path.parent):
                raise ValueError('unsafe financial evidence path')
            url = urlsplit(reference.get('url',''))
            if url.scheme != 'https' or not url.hostname or not reference.get('locator'):
                raise ValueError('financial evidence requires HTTPS URL and locator')
            if not re.fullmatch('[0-9a-f]{64}',reference.get('sha256','')):
                raise ValueError('invalid financial evidence hash')
            with target.open('rb') as stream:
                raw = stream.read(MAX_EVIDENCE_BYTES+1)
            read_bytes += len(raw)
            if read_bytes > MAX_EVIDENCE_BYTES:
                raise ValueError('financial evidence byte budget exceeded')
            if hashlib.sha256(raw).hexdigest() != reference['sha256']:
                raise ValueError('financial evidence checksum mismatch')
        verified[key] = d
    result = copy.deepcopy(payload)
    for row in result['financial_metrics']:
        d = verified.get((row['source_id'],row['stock_id'],row['period_end']))
        if d is None:
            continue  # No decision means no inferred currency, scope or conversion.
        amount = row['metric'] == 'monthly_revenue'
        row.update(raw_value=row['value'], raw_unit=d['raw_unit'] if amount else row['unit'],
                   normalization_version=VERSION, currency=d['currency'],
                   statement_scope=d['statement_scope'], consolidation=d['statement_scope'],
                   report_basis=d['report_basis'], value_basis=d['report_basis'],
                   normalization={'multiplier':1000 if amount else 1,
                       'raw_snapshot_sha256':d['raw_snapshot_sha256'],
                       'evidence_manifest_sha256':hashlib.sha256(body).hexdigest(),
                       'references':copy.deepcopy(d['references'])})
        if amount:
            if type(row['value']) is not int:
                raise ValueError('TWD thousand conversion requires exact integer source amount')
            row['value'] *= 1000
            row['unit'] = 'TWD'
    result['metadata'].update(normalization_version=VERSION,
        unit_policy='Only evidence-bound rows converted from TWD thousands; unreviewed rows retain source_reported.',
        unit_evidence_sha256=hashlib.sha256(body).hexdigest(),
        ledger_policy='separate_ledger_per_normalization_version_no_in_place_migration')
    return result
