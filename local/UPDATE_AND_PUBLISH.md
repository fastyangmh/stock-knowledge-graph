# Local after-close updates and branch-based GitHub Pages publication

## Architecture

Local SQLite is the source of truth. Run collectors locally (not included yet), normalize data to JSON, compute embeddings locally, export to `data/`, validate, then push only `data/`. Local validation runs before Git push. GitHub Pages publishes directly from main/root; GitHub Actions test.yml provides independent CI tests but does not gate deployment.

**Chosen deployment mode:** Settings → Pages → Source = **Deploy from a branch**, branch = main, folder = / (root). Do not switch to GitHub Actions deployment. Any direct push to main can still publish without waiting for CI; use the local validator and publisher.

## First-time setup

```bash
uv sync --extra dev
uv run pytest -q
uv run python -m local.validate_release
```

## Daily after-close workflow (Asia/Taipei)

1. Wait until the upstream provider has published official post-close data. Exchange holidays and delayed publications must be handled by your collector.
2. Run your local collectors to create a normalized input file (not yet implemented; **do not use sample_data.json for real updates**).
3. Import and calculate:
   ```bash
   uv run python -m local.pipeline all --semantic --input path/to/normalized.json --threshold 0.65
   uv run python -m local.validate_release
   uv run python -m local.publish --dry-run
   uv run python -m local.publish
   ```
4. Verify the Pages site after GitHub branch deployment and review the independent Python pipeline test workflow.

The publish command checks local main equals origin/main, refuses unrelated uncommitted changes, stages only `data/`, and pushes the validated export. It does not automatically collect data or know exchange holidays.

## Scheduler example (Linux cron, Asia/Taipei)

Only configure after confirming your data provider's post-close availability and local environment. Example at 18:30 Taipei time, Monday–Friday; the collector must independently skip exchange holidays:

```cron
CRON_TZ=Asia/Taipei
30 18 * * 1-5 cd /path/to/stock-knowledge-graph && /path/to/uv run python -m local.pipeline all --semantic --input /path/to/normalized.json --threshold 0.65 && /path/to/uv run python -m local.validate_release && /path/to/uv run python -m local.publish >> /path/to/stock-graph-update.log 2>&1
```

This cron line is **documentation only**, not an installed schedule. Real ingestion and exchange-calendar integration are not implemented.

## Safety

Never commit `*.db`, secrets, or licensed raw documents. Published JSON is public. Use a pinned model revision and a committed `uv.lock` before reproducible production runs. The GitHub workflow does not execute expensive local embeddings.
