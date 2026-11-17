"""Opt-in real model acceptance. Never invoked by local.check; private output only.

Three synthetic multilingual documents exercise the actual pinned model, SQLite,
research bundles and audit. This is not financial data or semantic quality validation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import subprocess
import sys
from unittest.mock import patch

from .bundle_audit import audit_bundle
from .core import ROOT, now
from .research import guarded, run
from .research_history import canonical
from .semantic import DEFAULT_MODEL

REVISION = 'e8f8c211226b894fcb81acc59f3b34ba3efd5f42'
MODEL_FILES = ('1_Pooling/config.json', 'config.json', 'config_sentence_transformers.json',
               'model.safetensors', 'modules.json', 'sentence_bert_config.json',
               'sentencepiece.bpe.model', 'special_tokens_map.json', 'tokenizer.json',
               'tokenizer_config.json', 'unigram.json')


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def prepare_model(destination, *, offline=False):
    """Download an immutable snapshot, or verify previously recorded Hub hashes.

Hub ETags identify LFS bytes by SHA256 and regular files by Git blob SHA1.
Offline evidence must originate from a prior successful online acquisition.
"""
    root = guarded(destination)
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / 'model-provenance.json'
    model = root / 'snapshot'
    if offline:
        manifest = json.loads(manifest_path.read_text())
        _require(manifest['model'] == DEFAULT_MODEL and manifest['revision'] == REVISION,
                 'model provenance identity differs')
        _require(set(manifest['files']) == set(MODEL_FILES), 'incomplete model provenance')
    else:
        from huggingface_hub import hf_hub_download, hf_hub_url, get_hf_file_metadata
        manifest = {'model': DEFAULT_MODEL, 'revision': REVISION, 'retrieved_at': now(),
                    'origin': 'https://huggingface.co/' + DEFAULT_MODEL, 'files': {}}
        for name in MODEL_FILES:
            metadata = get_hf_file_metadata(hf_hub_url(DEFAULT_MODEL, name, revision=REVISION), token=False)
            _require(metadata.commit_hash == REVISION, 'Hub revision differs')
            downloaded = Path(hf_hub_download(DEFAULT_MODEL, name, revision=REVISION,
                                             cache_dir=root / 'hub', token=False))
            target = model / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(downloaded, target)
            manifest['files'][name] = {'etag': metadata.etag, 'bytes': metadata.size}
    for name in MODEL_FILES:
        path = guarded(model / name)
        item = manifest['files'][name]
        _require(path.is_file() and path.stat().st_size == item['bytes'], 'model file size differs: ' + name)
        sha = _hash(path)
        if len(item['etag']) == 64:
            digest = sha
        else:
            _require(len(item['etag']) == 40, 'unsupported model ETag')
            digest = hashlib.sha1(b'blob ' + str(path.stat().st_size).encode() + b'\0' + path.read_bytes()).hexdigest()
        _require(digest == item['etag'], 'model file hash differs: ' + name)
        if offline:
            _require(sha == item['sha256'], 'model recorded SHA256 differs: ' + name)
        item['sha256'] = sha
    if not offline:
        manifest_path.write_bytes(canonical(manifest))
    return model, manifest


def fixture():
    observed = '2020-01-02T08:00:00+00:00'
    texts = [('晶片研究', '這是一篇合成測試文件：晶片設計與半導體製造。'),
             ('Chip research', 'Synthetic test document about semiconductor design and manufacturing.'),
             ('半導体の研究', 'これは合成テスト文書です。半導体の設計と製造を研究します。')]
    return {'stocks': [{'stock_id': f'TW:{1000+i}', 'ticker': str(1000+i), 'market': 'TW',
                        'name': f'Synthetic {i}'} for i in range(3)],
            'sources': [{'source_id': 'synthetic', 'provider': 'Synthetic model acceptance',
                         'url': 'https://example.org/model-fixture', 'license_type': 'synthetic-only'}],
            'documents': [{'document_id': f'd{i+1}', 'source_id': 'synthetic', 'doc_type': 'news',
                           'title': title, 'content': content, 'stock_ids': [f'TW:{1000+i}'],
                           'published_at': observed, 'available_at': observed}
                          for i, (title, content) in enumerate(texts)],
            'financial_metrics': [{'stock_id': 'TW:1000', 'source_id': 'synthetic',
                                   'metric': 'monthly_revenue', 'period_end': '2019-12-31',
                                   'period_type': 'month', 'value': 987654321, 'unit': 'source_reported',
                                   'available_at': observed}],
            'chip_metrics': [], 'metadata': {'observed_at': observed}}


def run_scenarios(destination, loader):
    """Run four isolated real research versions; loader is the encoder boundary."""
    root = guarded(destination)
    root.mkdir(parents=True, exist_ok=False)
    payload = fixture()
    results, previous_vectors, previous_edges, prior_hashes = [], {}, None, {}
    expected = [(3, 3, 1, 3), (0, 0, 0, 3), (1, 3, 1, 3), (0, 3, 0, 1)]
    for index, name in enumerate(('first', 'cached', 'text_changed', 'mapping_changed')):
        if index == 2:
            payload['documents'][0]['content'] = '合成測試修訂：太陽能與再生能源的研究。'
            payload['metadata']['observed_at'] = '2020-01-03T08:00:00+00:00'
        if index == 3:
            payload['documents'][0]['stock_ids'] = ['TW:1001']
            payload['metadata']['observed_at'] = '2020-01-04T08:00:00+00:00'
        source = root / (name + '.json')
        source.write_bytes(canonical(payload))
        loaded, encoded_texts = [], []

        class MeasuredEncoder:
            def __init__(self, encoder):
                self.encoder = encoder

            def get_sentence_embedding_dimension(self):
                dimension = getattr(self.encoder, 'get_embedding_dimension', None)
                return dimension() if dimension else self.encoder.get_sentence_embedding_dimension()

            def encode(self, texts, batch_size=32):
                encoded_texts.extend(texts)
                return self.encoder.encode(texts, batch_size=batch_size)

        def measured_loader(model_name, revision):
            _require(model_name == DEFAULT_MODEL and revision == REVISION, 'unexpected model request')
            loaded.append({'model': model_name, 'revision': revision})
            _require(index not in (1, 3), 'cache scenario attempted model loading')
            return MeasuredEncoder(loader())

        with patch('local.semantic.load_encoder', side_effect=measured_loader):
            report = run(source, ['1000', '1001', '1002'], history_db=root / 'history.db',
                         output_root=root / 'runs', analysis='semantic', model=DEFAULT_MODEL,
                         revision=REVISION, threshold=-1., top_k=2)
        bundle = audit_bundle(root / 'runs', report['run'])
        stats = report['analysis']
        actual = (stats['encoded'], stats['pairs_evaluated'], len(loaded), stats['stock_pairs'])
        _require(actual == expected[index], f'{name}: unexpected work counts {actual}')
        _require(stats['graph_reused'] == (index == 1), name + ': wrong graph reuse')
        _require(stats['model_loaded'] == bool(loaded), name + ': model load report differs')
        expected_texts = [d['title'] + '\n' + d['content'] for d in payload['documents']]
        _require(encoded_texts == (expected_texts if index == 0 else expected_texts[:1] if index == 2 else []),
                 name + ': unexpected encoded text / numeric input')
        database = root / 'runs' / report['run'] / 'graph.db'
        with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as conn:
            vectors = {node: hashlib.sha256(vector).hexdigest()
                       for node, vector in conn.execute('SELECT node_id,vector FROM embeddings ORDER BY node_id')}
        changed = sorted(n for n in vectors if n in previous_vectors and vectors[n] != previous_vectors[n])
        _require(changed == (['doc:d1'] if index == 2 else []), name + ': unexpected vector changes')
        edges = {e['id']: e for graph in bundle.graphs.values() for e in graph['edges']
                 if e['relation'] == 'semantic_similarity'}
        _require(all(e['evidence_ids'] for e in edges.values()), name + ': missing semantic evidence')
        links = {d['document_id']: set(d['stock_ids']) for d in payload['documents']}
        for edge in edges.values():
            if edge['source'].startswith('stock:') and edge['target'].startswith('stock:'):
                a, b = edge['evidence_ids']
                source, target = edge['source'][6:], edge['target'][6:]
                _require((source in links[a] and target in links[b]) or
                         (target in links[a] and source in links[b]), 'stock evidence does not match mapping')
        if index == 1:
            _require(edges == previous_edges, 'cached graph differs')
        if index == 3:
            _require(edges != previous_edges, 'mapping did not change exported relationships')
            _require(not any(e['source'] == 'stock:TW:1000' or e['target'] == 'stock:TW:1000'
                             for e in edges.values()), 'stale stock mapping evidence')
        for path, digest in prior_hashes.items():
            _require(_hash(path) == digest, 'old bundle was modified')
        for path in database.parent.rglob('*'):
            if path.is_file():
                prior_hashes[path] = _hash(path)
        results.append({'scenario': name, 'analysis': stats, 'loader_calls': len(loaded),
                        'encoded_text_sha256': [hashlib.sha256(t.encode()).hexdigest() for t in encoded_texts],
                        'vector_sha256': vectors, 'changed_vectors': changed, 'numeric_excluded': True,
                        'semantic_edges': list(edges.values()), 'audit': bundle.summary(), 'exit_code': 0})
        previous_vectors, previous_edges = vectors, edges
        (root / 'scenarios.json').write_bytes(canonical(results))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New private directory; refuses overwrite')
    parser.add_argument('--model-cache', type=Path, required=True)
    parser.add_argument('--offline', action='store_true', help='Require a previously verified model cache')
    args = parser.parse_args(argv)
    output, cache = guarded(args.output), guarded(args.model_cache)
    _require(not output.exists(), 'output already exists; choose a new directory')
    _require(output != cache and not output.is_relative_to(cache) and not cache.is_relative_to(output),
             'model cache and output must be separate')
    output.mkdir(parents=True)
    report = {'started_at': now(), 'model': DEFAULT_MODEL, 'revision': REVISION,
              'command': [sys.executable, '-m', 'local.model_check', *(sys.argv[1:] if argv is None else argv)],
              'scope': 'real model; synthetic multilingual documents and numeric fixture; no financial validation',
              'acquisition': 'verified_cache' if args.offline else 'pinned_hub_download',
              'environment': {'os': platform.system(), 'architecture': platform.machine(),
                              'processor': platform.processor(), 'cpu_count': os.cpu_count(), 'python': platform.python_version(),
                              'device': 'cpu', 'packages': {p: importlib.metadata.version(p) for p in
                                  ('sentence-transformers', 'torch', 'transformers', 'huggingface-hub', 'numpy')}},
              'lock_sha256': _hash(ROOT / 'uv.lock'), 'source_sha256': _hash(Path(__file__)),
              'commands': {}, 'passed': False, 'exit_code': 1,
              'linux_target_acceptance': False}
    for name, command in {'commit': ['git', 'rev-parse', 'HEAD'], 'dirty': ['git', 'status', '--porcelain'],
                          'uv': ['uv', '--version'], 'node': ['node', '--version']}.items():
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=10)
            report['commands'][name] = {'command': command, 'exit_code': result.returncode,
                                         'output': result.stdout + result.stderr}
        except (OSError, subprocess.TimeoutExpired) as exc:
            report['commands'][name] = {'command': command, 'exit_code': None, 'error': str(exc)}
    try:
        model, provenance = prepare_model(cache, offline=args.offline)
        report['model_provenance'] = provenance
        from sentence_transformers import SentenceTransformer
        import torch
        torch.set_num_threads(1)
        report['environment']['torch_threads'] = torch.get_num_threads()
        report['scenarios'] = run_scenarios(output / 'exercise', lambda: SentenceTransformer(
            str(model), device='cpu', local_files_only=True, trust_remote_code=False))
        report.update(passed=True, exit_code=0)
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)}
    report['finished_at'] = now()
    (output / 'report.json').write_bytes(canonical(report))
    print(json.dumps({'passed': report['passed'], 'report': str(output / 'report.json'),
                      'error': report.get('error')}, ensure_ascii=False))
    return report['exit_code']


if __name__ == '__main__':
    sys.exit(main())
