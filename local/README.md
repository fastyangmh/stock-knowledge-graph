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
