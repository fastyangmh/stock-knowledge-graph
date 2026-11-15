# Local SQLite → JSON pipeline

Requires **Python 3.10+**, standard library only.

From repository root:

```bash
python -m local.pipeline all
python -m local.pipeline validate
python -m http.server 8000
```

Open http://localhost:8000 . This uses **synthetic sample data**; it is not financial advice or real market data.

Commands:
- `init`: create SQLite schema
- `import --input path/to/normalized.json`: idempotent import
- `similarity --top-k 10 --threshold 0.15`: compute baseline lexical similarity
- `export`: generate JSON compatible with existing frontend
- `all`: import + similarity + export
- `validate`: check graph endpoint integrity

`--db`, `--output`, `--input` override paths.

**Important limitations:** The built-in similarity is **character-bigram lexical cosine**, not an ML semantic embedding. It provides a zero-dependency working pipeline and deterministic test baseline. Real financial semantic analysis requires selecting and validating a multilingual/financial embedding model. Current neighbor search is quadratic in document count; use ANN/FAISS for larger datasets. The stock similarity is a *maximum* document-pair lexical score, not price correlation or causation.

Keep local DB files, API tokens and restricted news content out of the public repository. `data/` JSON is publicly downloadable. For financial backtesting, use publication availability timestamps and preserve revision history.

## Production-style local multilingual embeddings (optional)

Install the separate dependency in a local Python environment:

```bash
python -m pip install -r local/requirements-embedding.txt
python -m local.pipeline import --input local/sample_data.json
python -m local.pipeline semantic --model sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 --top-k 10 --threshold 0.65
python -m local.pipeline export
python -m local.pipeline validate
python -m unittest discover -s local/tests -v
```

Or run import, semantic similarity and export together:

```bash
python -m local.pipeline all --semantic --threshold 0.65
```

The model downloads on first local use; later runs use the local model cache. You can provide `--revision <commit-sha>` to pin a specific Hugging Face model revision. The default multilingual MiniLM model is a practical baseline, **not** a finance-specialized or validated model.

### Embedding cache and incremental updates

- Cache key: model identity (model name + optional revision + input template version), document node ID, and hash of title + content.
- Unchanged documents reuse float32 embeddings from SQLite without calling the encoder.
- Changed or new documents are encoded in batches (`--batch-size 32`).
- The similarity graph is recomputed for the selected model after cache refresh, because a new document may alter existing Top-K neighbors. This is **incremental embedding**, not yet incremental nearest-neighbor indexing.
- Only the selected model's edges are replaced; explicit relationships and other models' edges are preserved.
- Stock-to-stock score currently aggregates by maximum linked document-pair cosine, which can overstate relevance; treat as an exploratory signal.

**Scale limitation:** Exact all-pairs similarity is O(N²). For large news corpora add an ANN index such as FAISS and date/category candidate filters before production deployment. The optional encoder uses CPU by default when no compatible accelerator is available. For research reproducibility, pin model revision and dependency versions.

## uv environment management (preferred)

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and run from repository root:

```bash
uv python install 3.11
uv sync --extra dev
uv run python -m local.pipeline all --semantic --top-k 10 --threshold 0.65
uv run python -m local.pipeline validate
uv run pytest -q
```

`pyproject.toml` manages dependencies; `.python-version` selects Python 3.11. `uv sync` creates a local `.venv` automatically. To make installs reproducible, run `uv lock` and commit the generated `uv.lock`. Until the lockfile is committed, dependency resolution may change across machines or CI runs. The older `requirements-embedding.txt` remains only for compatibility; prefer uv commands above.

## CI and release safeguards

GitHub Actions now runs offline unit tests and an isolated CLI smoke test using `/tmp/stock-graph-ci.db` and `/tmp/stock-graph-ci-json`. This does not publish test JSON to GitHub Pages.

Before production publication, validate every exported graph and review data licensing. A successful push to `main` is a publication action because GitHub Pages serves `data/` publicly.

The SQLite database is excluded from Git. Do not commit the model cache, private source documents or access tokens. To reproduce the Python environment, generate and commit `uv.lock` in an environment with package-index access, then use `uv sync --locked --extra dev`.

**Verification status:** CI workflow has been configured, but passing CI and an actual downloaded Sentence Transformers model run must be confirmed separately.
