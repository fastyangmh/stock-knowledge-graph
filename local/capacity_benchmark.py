"""Private, reproducible CPU measurements of exact search on synthetic multilingual documents."""
from __future__ import annotations

import argparse
from contextlib import closing
from copy import deepcopy
import hashlib
import json
from importlib.metadata import version
import multiprocessing
import os
from pathlib import Path
import platform
import random
import resource
import sqlite3
import subprocess
import sys
import time

from .collect_official import atomic_bytes
from .core import ROOT
from .model_check import fixture, prepare_model, REVISION
from .research import file_digest, guarded, run
from .research_history import canonical
from .semantic import DEFAULT_MODEL


def compare_exact(names, vectors, observed, *, top_k, threshold):
    """Independent float64 cosine and full per-document sorting; compare undirected union."""
    import numpy as np

    matrix = np.asarray(vectors, dtype=np.float64)
    norms = np.linalg.norm(matrix, axis=1)
    if len(names) != len(matrix) or not np.isfinite(norms).all() or (norms == 0).any():
        raise ValueError('invalid baseline vector')
    matrix = matrix / norms[:, None]
    expected = {}
    for i, name in enumerate(names):
        scores = np.clip(matrix @ matrix[i], -1., 1.)
        eligible = [j for j in range(len(names)) if i != j and scores[j] >= threshold]
        for j in sorted(eligible, key=lambda j: (-scores[j], names[j]))[:top_k]:
            expected[tuple(sorted((name, names[j])))] = float(scores[j])
    matched = observed.keys() & expected.keys()
    error = max((abs(observed[p] - expected[p]) for p in matched), default=None)
    return {'expected_pairs': len(expected), 'stored_pairs': len(observed),
            'missing_pairs': len(expected) - len(matched), 'extra_pairs': len(observed) - len(matched),
            'recall': len(matched) / len(expected) if expected else None,
            'max_absolute_score_error': error,
            'passed': observed.keys() == expected.keys() and (error is None or error <= .00000051)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', type=int, nargs='+', default=[32, 128, 512])
    parser.add_argument('--max-pairs', type=int, default=130_816)
    parser.add_argument('--seed', type=int, default=20261119)
    parser.add_argument('--output', type=Path, required=True, help='New private directory')
    parser.add_argument('--model-cache', type=Path, required=True, help='Verified local.model_check cache')
    args = parser.parse_args(argv)
    if min(args.sizes) < 2 or len(set(args.sizes)) != len(args.sizes):
        raise ValueError('sizes must be distinct document counts of at least two')
    for size in args.sizes:
        pairs = size * (size - 1) // 2
        if pairs > args.max_pairs:
            raise ValueError(f'{size} documents: {pairs} candidate pairs exceed budget {args.max_pairs}')

    output, cache = guarded(args.output), guarded(args.model_cache)
    if output.exists():
        raise FileExistsError('select a new benchmark directory')
    if output.is_relative_to(cache) or cache.is_relative_to(output):
        raise ValueError('keep benchmark output and verified model cache separate')
    if not (cache / 'model-provenance.json').is_file():
        raise FileNotFoundError('verified offline model cache required')
    snapshot, _ = prepare_model(cache, offline=True)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = {'passed': False, 'seed': args.seed, 'sizes': args.sizes, 'max_pairs': args.max_pairs,
              'command': [sys.executable, '-m', 'local.capacity_benchmark', *(sys.argv[1:] if argv is None else argv)],
              'model': DEFAULT_MODEL, 'revision': REVISION, 'device': 'cpu', 'torch_threads': 1,
              'model_provenance_sha256': file_digest(cache / 'model-provenance.json'),
              'lock_sha256': file_digest(ROOT / 'uv.lock'), 'environment': environment(), 'phases': []}
    try:
        for size in args.sizes:
            folder = output / str(size)
            folder.mkdir()
            checksum = write_workload(folder / 'input.json', size, args.seed)
            for mode in ('cold', 'hot'):
                start = time.perf_counter()
                process = multiprocessing.get_context('spawn').Process(
                    target=phase_worker, args=(folder, mode, args.max_pairs, snapshot))
                process.start()
                process.join()
                elapsed = time.perf_counter() - start
                if process.exitcode:
                    raise RuntimeError(f'{size} {mode} research worker exited {process.exitcode}')
                row = json.loads((folder / f'{mode}.json').read_bytes())
                row.update(documents=size, mode=mode, input_sha256=checksum, process_seconds=elapsed)
                row['exact'] = verify_phase(folder, row, size=size, mode=mode)
                report['phases'].append(row)
                if not row['exact']['passed']:
                    raise ValueError(f'{size} {mode} differs from exhaustive reference')
        report['passed'] = True
    finally:
        atomic_bytes(output / 'summary.json', canonical(report))
    print(output / 'summary.json')
    return 0


def environment():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()

    cpu = platform.processor()
    if sys.platform == 'darwin':
        cpu = subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
    elif Path('/proc/cpuinfo').is_file():
        cpu = next((line.partition(':')[2].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                    if line.startswith('model name')), cpu)
    return {'os': platform.platform(), 'architecture': platform.machine(), 'cpu': cpu,
            'cpu_count': os.cpu_count(), 'python': platform.python_version(),
            'packages': {p: version(p) for p in ('sentence-transformers', 'torch', 'numpy', 'transformers')},
            'commit': git('rev-parse', 'HEAD'), 'dirty': bool(git('status', '--porcelain'))}


def phase_worker(folder, mode, max_pairs, snapshot):
    # Set before importing torch, tokenizer or model code. The hot path imports none of these.
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false',
                      OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')

    def load(name, revision):
        if name != DEFAULT_MODEL or revision != REVISION:
            raise ValueError('unexpected model identity')
        import torch
        from sentence_transformers import SentenceTransformer
        torch.set_num_threads(1)
        return SentenceTransformer(str(snapshot), device='cpu', local_files_only=True, trust_remote_code=False)

    result = measure_phase(folder, max_pairs=max_pairs, encoder_loader=load)
    atomic_bytes(folder / f'{mode}.json', canonical(result))


def write_workload(path, size, seed):
    randomizer = random.Random(seed)
    payload = fixture()
    templates = payload['documents']
    documents = []
    for i in range(size):
        doc = deepcopy(templates[i % len(templates)])
        doc['document_id'] = f'capacity-{i:04d}'
        doc['content'] += f' {randomizer.randrange(100_000)} {i}'
        documents.append(doc)
    payload['documents'] = documents
    data = canonical(payload)
    with guarded(path).open('xb') as stream:
        stream.write(data)
    return hashlib.sha256(data).hexdigest()


def measure_phase(root, *, max_pairs, encoder_loader):
    """Run one complete research build. Start a fresh process per call for independent peak RSS."""
    start = time.perf_counter()
    report = run(root / 'input.json', ['1000', '1001', '1002'],
                 history_db=root / 'ledger.db', output_root=root / 'runs',
                 analysis='semantic', model=DEFAULT_MODEL, revision=REVISION,
                 max_pairs=max_pairs, encoder_loader=encoder_loader)
    elapsed = time.perf_counter() - start
    usage = resource.getrusage(resource.RUSAGE_SELF)
    bundle = root / 'runs' / report['run']
    json_files = list(bundle.rglob('*.json'))
    return {'run': report['run'], 'analysis': report['analysis'], 'research_seconds': elapsed,
            'user_cpu_seconds': usage.ru_utime, 'system_cpu_seconds': usage.ru_stime,
            'peak_rss_bytes': usage.ru_maxrss * (1 if sys.platform == 'darwin' else 1024),
            'bundle_json_bytes': sum(p.stat().st_size for p in json_files),
            'display_json_bytes': sum(p.stat().st_size for p in json_files if p.is_relative_to(bundle / 'data'))}


def verify_phase(root, row, *, size, mode):
    """Read the saved database and independently check active document IDs, cache work and scores."""
    import numpy as np

    bundle = root / 'runs' / row['run']
    analysis = row['analysis']
    config = json.loads((bundle / 'report.json').read_bytes())['configuration']['analysis']
    expected_work = (size, 0, size * (size - 1) // 2, True, False) if mode == 'cold' else (0, size, 0, False, True)
    work = tuple(analysis[key] for key in ('encoded', 'cache_hits', 'pairs_evaluated', 'model_loaded', 'graph_reused'))
    if work != expected_work:
        raise ValueError(f'{mode} cache work differs: {work}')
    with closing(sqlite3.connect((bundle / 'graph.db').as_uri() + '?mode=ro', uri=True)) as db:
        rows = db.execute('SELECT node_id, vector FROM embeddings WHERE model_id=? ORDER BY node_id',
                          (analysis['model_id'],)).fetchall()
        edges = {(a, b): score for a, b, score in db.execute(
            "SELECT source_id,target_id,score FROM graph_edges WHERE method='sentence_transformers_cosine' AND model_id=?",
            (analysis['model_id'],))}
    names = [name for name, _ in rows]
    if set(names) != {f'doc:capacity-{i:04d}' for i in range(size)}:
        raise ValueError('saved embedding IDs differ from requested workload')
    vectors = np.stack([np.frombuffer(blob, dtype='<f4') for _, blob in rows])
    return compare_exact(names, vectors, edges, top_k=config['top_k'], threshold=config['threshold'])


if __name__ == '__main__':
    raise SystemExit(main())
