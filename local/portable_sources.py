"""Replay reviewed source adapters from the files in a portable archive."""
import hashlib
from collections import defaultdict
from pathlib import Path

from . import announcement_import, institutional_import, margin_import, news_industry, quarterly_cashflow, quarterly_import
from .dates import timestamp
from .source_receipts import ADAPTERS, registry
from .combined_universe import ETF, TW50, load_combined_universe
from .official_adapter import from_snapshots
from .research_history import canonical, strict_json_value
from .source_registry import load_approved


class SourceInputs:
    def __init__(self, root, files, refs):
        self.root = root
        self.refs = refs
        self.monthly = {}
        self.registries = []
        self.offline_receipts = {}
        self.reviews = defaultdict(list)
        self.normalized_inputs = [item for item in files if item['class'] == 'normalized_input']
        for entry in files:
            path = Path(entry['path'])
            if path.name == 'retrieval_manifest.json' and entry['class'] == 'raw':
                if entry['bytes'] > 4*1024**2:
                    raise ValueError('financial retrieval receipt exceeds replay budget')
                doc = strict_json_value((root/path).read_bytes())
                datasets = doc.get('datasets', [])
                if datasets and all('dataset_id' in row for row in datasets):
                    fields = ('dataset_id', 'retrieved_at', 'resource_url', 'sha256', 'bytes')
                    key = canonical([{k: row[k] for k in fields} for row in datasets])
                    self.monthly[key] = entry
            elif entry['class'] in ('raw', 'configuration') and path.suffix == '.json' and entry['bytes'] <= 4*1024**2:
                try:
                    doc = strict_json_value((root/path).read_bytes())
                except (ValueError, UnicodeError):
                    continue  # Opaque attachments can include a captured error or an invalid response.
                if isinstance(doc, list) and entry['class'] == 'raw':
                    for row in doc:
                        if isinstance(row, dict) and type(row.get('id')) is int and 'received_at' in row and 'sha256' in row:
                            key = (row['id'], row['sha256'], timestamp(row['received_at']))
                            self.offline_receipts[key] = entry
                if isinstance(doc, dict) and 'raw_sha256' in doc and type(doc.get('record')) is int:
                    self.reviews[doc['raw_sha256'], doc['record']].append((entry, doc))
                if entry['class'] == 'configuration' and isinstance(doc, list) and doc and all(isinstance(row, dict) and 'dataset_id' in row for row in doc):
                    ids = {row['dataset_id'] for row in load_approved(root/path)}
                    self.registries.append((entry, ids))

    def target(self, owner, field, entry):
        self.refs.record(owner, field, entry['sha256'], entry['path'])
        return self.root/entry['path']

    def attachment(self, owner, field, checksum):
        return self.root/self.refs.require_file(owner, field, checksum, {'raw', 'configuration'})

    def monthly_payload(self, payload, owner):
        meta = payload['metadata']
        snapshots = meta['source_snapshots']
        manifest = self.monthly.get(canonical(snapshots))
        ids = {s['dataset_id'] for s in snapshots}
        if manifest is None:
            raise ValueError('missing matching retrieval_manifest.json for official monthly replay')
        registries = [entry for entry, enabled in self.registries if ids <= enabled]
        if not registries:
            raise ValueError('missing approved financial source registry for monthly replay')
        root = self.target(owner, 'acquisition_receipt_sha256', manifest).parent
        unit = (self.attachment(owner, 'unit_evidence_sha256', meta['unit_evidence_sha256'])
                if 'unit_evidence_sha256' in meta else None)
        selection = {s['stock_id'] for s in payload['stocks']}
        for registry in registries:
            rebuilt = from_snapshots(root, self.root/registry['path'], selection,
                                     as_of=meta['universe_as_of'], unit_evidence=unit)
            if 'research_selection' in meta:
                rebuilt['metadata']['research_selection'] = dict(mode='explicit_symbols_not_index_membership',
                                                                stock_ids=sorted(selection))
            if 'research_universe' in meta:
                hashes = meta['research_universe']['input_sha256']
                constituents = self.attachment(owner, 'universe_input_sha256', hashes[TW50])
                holdings = self.attachment(owner, 'universe_input_sha256', hashes[ETF])
                urls = {item['source_url'] for stock in payload['stocks'] for item in stock['universe_memberships']
                        if item['universe_id'] == TW50}
                if len(urls) != 1:
                    raise ValueError('ambiguous TW50 evidence URL')
                rebuilt = load_combined_universe(constituents, holdings, meta['universe_as_of'], urls.pop()).annotate_payload(rebuilt)
            if canonical(rebuilt) == canonical(payload):
                self.target(owner, 'source_registry_sha256', registry)
                return
        raise ValueError('official monthly replay differs from ledger snapshot')

    def announcement(self, payload, owner, manifest, dataset, snapshot):
        records = payload['metadata']['records']
        record = records[0]['csv_records'][0] if len(records) == 1 else None
        review = parent = None
        if 'source_revision' in payload or any('reviewed_links' in row for row in records):
            revision = payload.get('source_revision')
            if revision:
                for entry in self.normalized_inputs:
                    path = self.root/entry['path']
                    body = quarterly_import.read_bytes(path)
                    if hashlib.sha256(canonical(strict_json_value(body))).hexdigest() == revision['target_snapshot_sha256']:
                        parent = path
                        break
                if parent is None:
                    raise ValueError('missing reviewed announcement parent input')
            for entry, candidate in self.reviews[snapshot['sha256'], record]:
                expected = ({'action': revision['action'], 'target_document_id': revision['key']['document_id'],
                             'evidence': revision['evidence'], 'target_snapshot_sha256': revision['target_snapshot_sha256']}
                            if revision else records[0]['reviewed_links'])
                if candidate.get('revision' if revision else 'links') == expected:
                    self.target(owner, 'announcement_review_sha256', entry)
                    review = candidate
                    break
            if review is None:
                raise ValueError('missing announcement review for selected record')
        return announcement_import.normalize(manifest, dataset, record, review, parent)

    def validate(self, payload, owner):
        meta = payload['metadata']
        version = meta.get('adapter_version')
        if version == 'official-csv-v1':
            self.monthly_payload(payload, owner)
            return
        if version == 'issuer-cashflow-notes-v1':
            notes = self.attachment(owner, 'note_sha256', meta['note_sha256'])
            rebuilt = quarterly_cashflow.normalize(quarterly_import.read_bytes(notes), meta['note_sha256'])
        elif version in ADAPTERS or version == 'mops-quarterly-v1':
            snapshot, = meta['source_snapshots']
            source = registry()[snapshot['dataset_id']]
            dataset = int(source['dataset_url'].rsplit('/', 1)[-1])
            entry = self.offline_receipts.get((dataset, snapshot['sha256'], timestamp(snapshot['retrieved_at'])))
            if entry is None:
                raise ValueError('missing original offline acquisition receipt for ' + snapshot['dataset_id'])
            manifest = self.target(owner, 'acquisition_receipt_sha256', entry)
            symbols = [s['ticker'] for s in payload['stocks']]
            if version == 'mops-quarterly-v1':
                rebuilt = quarterly_import.normalize(manifest, dataset, symbols)
                if sha := meta.get('review_sha256'):
                    proof = self.attachment(owner, 'review_sha256', sha)
                    quarterly_import.apply_review(rebuilt, dataset, quarterly_import.read_bytes(proof))
            elif version.startswith(('tpex-institutional-', 'tpex-margin-')):
                adapter = margin_import if version.startswith('tpex-margin-') else institutional_import
                rebuilt = adapter.normalize(manifest, meta['trade_date'], {'TW:'+s for s in symbols})
                if version.endswith('-1'):
                    del rebuilt['source_csv_b64']
                    rebuilt['metadata']['adapter_version'] = version
                    for stock in rebuilt['stocks']:
                        for field in ('provider', 'raw_sha256', 'row_number', 'source_column'):
                            del stock[field]
            elif version == 'mops-announcement-1':
                rebuilt = self.announcement(payload, owner, manifest, dataset, snapshot)
            else:
                rebuilt = news_industry.normalize(manifest, dataset)
            if version in ('official-industry-v1', 'mops-announcement-1'):
                original_fields = {'stock_id', 'market', 'ticker', 'name'}
                if all(stock.keys() == original_fields for stock in payload['stocks']):
                    rebuilt['stocks'] = [{k: row[k] for k in original_fields} for row in rebuilt['stocks']]
        else:
            # A private custom adapter may have only a normalized snapshot as its source.
            return
        if canonical(rebuilt) != canonical(payload):
            raise ValueError('restored source replay differs from ledger snapshot: ' + version)
