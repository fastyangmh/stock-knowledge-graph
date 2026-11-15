"""Exact, deterministic undirected Top-K union with O(N*K) candidate storage.

This bounds memory, not the O(N*N*dimension) comparison cost. Union Top-K is
not a strict graph degree cap; the display lifecycle imposes its own caps.
"""
from __future__ import annotations
import heapq
import math
from collections.abc import Mapping, Sequence


def top_k_pairs(vectors: Mapping[str, Sequence[float]], k: int, threshold: float,
                *, max_pairs: int = 2_000_000) -> tuple[dict[tuple[str, str], float], dict]:
    if type(k) is not int or k < 1 or not math.isfinite(threshold) or not -1 <= threshold <= 1:
        raise ValueError("invalid top_k or threshold")
    if type(max_pairs) is not int or max_pairs < 0:
        raise ValueError("max_pairs must be a nonnegative integer")
    ids = sorted(vectors)
    count = len(ids) * (len(ids) - 1) // 2
    if count > max_pairs:
        raise ValueError(f"{count} candidate pairs exceed budget {max_pairs}; narrow the active window")
    data = [tuple(float(x) for x in vectors[nid]) for nid in ids]
    if data:
        dimension = len(data[0])
        for vector in data:
            if not vector or len(vector) != dimension or not all(map(math.isfinite, vector)):
                raise ValueError("invalid vector or inconsistent dimension")
            if not math.isclose(math.fsum(x*x for x in vector), 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise ValueError("Top-K requires unit-normalized, nonzero vectors")
    heaps: list[list[tuple[float, int]]] = [[] for _ in ids]
    def keep(i: int, j: int, score: float) -> None:
        item = (score, -j)  # Lower lexical ID wins a tie.
        if len(heaps[i]) < k:
            heapq.heappush(heaps[i], item)
        elif item > heaps[i][0]:
            heapq.heapreplace(heaps[i], item)
    for i, a in enumerate(data):
        for j in range(i + 1, len(data)):
            score = max(-1.0, min(1.0, math.fsum(x*y for x, y in zip(a, data[j]))))
            if score >= threshold:
                keep(i, j, score)
                keep(j, i, score)
    result = {}
    for i, heap in enumerate(heaps):
        for score, neg_j in heap:
            j = -neg_j
            result[(ids[min(i, j)], ids[max(i, j)])] = score
    return dict(sorted(result.items())), {
        "pairs_evaluated": count,
        "retained_candidates": sum(map(len, heaps)),
    }
