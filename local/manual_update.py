"""Run a private, manually requested update for one market."""
import argparse
import re
import shutil
import sys
import uuid
from pathlib import Path
from zoneinfo import ZoneInfo

from . import research
from .bundle_audit import audit_bundle, pending_pointer
from .manual_sources import closed_day_evidence, financial_sources, ingest_prices, normalize, read_json, optional_json
from .calendar_coverage import calendar_day, load_calendar
from .collect_official import atomic_bytes
from .dates import iso_date, timestamp
from .market_prices import FEEDS
from .research import guarded
from .research_history import canonical, utc_now, validate_symbols
from .safety import exclusive_lock

STAGES = ('preflight', 'calendar', 'acquire', 'normalize', 'prices', 'research', 'audit')


def preflight(plan, report):
    fields = {'market', 'symbols', 'trade_date', 'as_of', 'calendar', 'registry', 'financial_dir',
              'financial_manifest_sha256', 'price_file', 'price_sha256', 'download_financial', 'download_prices',
              'expected_revenue_month', 'unit_evidence', 'unit_evidence_sha256', 'min_free_bytes', 'analysis', 'revision'}
    if unknown := set(plan) - fields:
        raise ValueError('unrecognized plan fields: ' + ', '.join(sorted(unknown)))
    validate_symbols(plan['symbols'])
    if plan.get('analysis', 'none') not in ('none', 'lexical', 'semantic'):
        raise ValueError('unknown research analysis mode')
    if plan.get('analysis') == 'semantic' and not re.fullmatch('[a-f0-9]{40}', plan.get('revision', '')):
        raise ValueError('semantic research requires a pinned model revision')
    today = timestamp(utc_now()).astimezone(ZoneInfo('Asia/Taipei')).date()
    if iso_date(plan['trade_date']) > today or iso_date(plan['as_of']) > today:
        raise ValueError('future trade date or acquisition day')
    if 'expected_revenue_month' in plan:
        iso_date(plan['expected_revenue_month'] + '-01')
    for field in ('calendar', 'registry', 'financial_dir', 'price_file', 'unit_evidence'):
        if field in plan and not Path(plan[field]).is_absolute():
            raise ValueError('plan paths must be absolute: ' + field)
    for flag, path in [('download_financial', 'financial_dir'), ('download_prices', 'price_file')]:
        if type(plan.get(flag, False)) is not bool or (plan.get(flag) and path in plan):
            raise ValueError('ambiguous or invalid acquisition mode: ' + flag)
    minimum = plan.get('min_free_bytes', 0)
    if type(minimum) is not int or minimum < 0:
        raise ValueError('min_free_bytes must be a nonnegative integer')
    report['disk']['min_free_bytes'] = minimum
    if report['disk']['free'] < minimum:
        report['stages']['preflight']['kind'] = 'low_disk'
        raise ValueError('available disk space is below the requested minimum')


def update(plan, market, job, through, report):
    report['stage'] = 'preflight'
    preflight(plan, report)
    report['stages']['preflight']['status'] = 'success'
    if through == 'preflight':
        return
    report['stage'] = 'calendar'
    entries, _ = load_calendar(plan['calendar'], timestamp(utc_now()), 256*1024**2)
    report['calendar'] = calendar_day(entries, plan['market'], iso_date(plan['trade_date']))
    if report['calendar']['market_status'] == 'closed' and plan.get('price_file'):
        closed_day_evidence(plan, report['calendar'])
    state = report['calendar']['market_status']
    if state not in ('open', 'closed'):
        report['stages']['calendar']['kind'] = state
        raise ValueError('market calendar status: ' + state)
    report['stages']['calendar']['status'] = 'success'
    if state == 'closed' or through == 'calendar':
        return
    report['stage'] = 'acquire'
    snapshots, registry = financial_sources(plan, job, report['stages']['acquire'])
    report['stages']['acquire']['status'] = 'success'
    if through == 'acquire':
        return
    report['stage'] = 'normalize'
    detail = normalize(plan, snapshots, registry, job, report['stages']['acquire']['sources'])
    report['stages']['normalize'].update(status='success', **detail)
    if through == 'normalize':
        return
    report['stage'] = 'prices'
    report['stages']['prices']['source'] = FEEDS[plan['market']]['source_id']
    report['stages']['prices'].update(status='success', **ingest_prices(plan, market, job))
    if through == 'prices':
        return
    report['stage'] = 'research'
    candidate = guarded(job/'candidate')
    runs = guarded(market/'runs')
    pointer_path = guarded(runs/'latest.json')
    base_path = guarded(job/'baseline.json')
    if not base_path.exists():
        atomic_bytes(base_path, canonical({'pointer': optional_json(pointer_path)}))
    previous = read_json(base_path)['pointer']
    if not guarded(candidate/'latest.json').exists():
        research.run(job/'input.json', plan['symbols'], history_db=guarded(market/'ledger.db'),
                     output_root=candidate, prices_db=guarded(market/'prices.db'), price_snapshots=market/'prices',
                     trade_date=plan['trade_date'], price_market=plan['market'], alerts=True,
                     analysis=plan.get('analysis', 'none'), revision=plan.get('revision'))
    current = optional_json(pointer_path)
    try:
        pointer = read_json(candidate/'latest.json')
        if (not re.fullmatch(r'[0-9a-f]{32}', pointer['run']) or
                not re.fullmatch(r'[0-9a-f]{64}', pointer['report_sha256']) or
                pointer.get('engine') != research.ENGINE_VERSION):
            raise ValueError('invalid candidate pointer')
        final = guarded(runs/pointer['run'])
        bundle_root = runs if final.exists() else candidate
        pending = optional_json(pending_pointer(runs, pointer['run']))
        if final.exists() and pending != pointer and (current != pointer or previous == pointer):
            raise ValueError('candidate points to a different published job')
        bundle = audit_bundle(bundle_root, pointer['run'], expected_report_sha=pointer['report_sha256'],
                              allow_pending=pending == pointer)
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        candidate.rename(guarded(job/('rejected-candidate-'+uuid.uuid4().hex)))
        raise
    report['stages']['research'].update(status='success', run=pointer['run'])
    if through != 'research':
        report['stage'] = 'audit'
    if current not in (previous, pointer):
        raise ValueError('another job advanced the last success pointer')
    if bundle.report['input_sha256'] != detail['input_sha256'] or bundle.alerts is None:
        raise ValueError('candidate input or alerts mismatch')
    prices = report['stages']['prices']
    observations = bundle.report['market_observations']
    if ({row['symbol'] for row in observations} != set(plan['symbols']) or
            any(row['raw_sha256'] != prices['raw_sha256'] or row['trade_date'] != plan['trade_date']
                or row['observed_at'] != prices['observed_at'] or row['source_id'] != prices['source']
                for row in observations)):
        raise ValueError('candidate price evidence differs from the verified job input')
    if through == 'research':
        return
    runs.mkdir(exist_ok=True, mode=0o700)
    report['stages']['audit'].update(status='success', run=pointer['run'])
    return pointer


def save_report(job, report):
    body = canonical(report)
    atomic_bytes(guarded(job/'attempts'/(report['attempt']+'.json')), body)
    atomic_bytes(guarded(job/'report.json'), body)


def execute(plan, market, job, through):
    pointer_path = guarded(market/'runs/latest.json')
    previous_success = None
    report = {'market': plan['market'], 'trade_date': plan.get('trade_date'), 'job': job.name,
              'attempt': uuid.uuid4().hex, 'started_at': utc_now(), 'through': through,
              'stage': 'preflight', 'last_success': None,
              'stages': {s: {'status': 'skipped'} for s in STAGES}}
    current = None
    try:
        report['disk'] = shutil.disk_usage(job)._asdict()
        current = optional_json(pointer_path)
        if current is not None:
            if current.get('engine') != research.ENGINE_VERSION or not re.fullmatch('[0-9a-f]{64}', current['report_sha256']):
                raise ValueError('invalid last success pointer')
            audit_bundle(pointer_path.parent, current['run'], expected_report_sha=current['report_sha256'])
            previous_success = report['last_success'] = current['run']
        saved_plan = guarded(job/'plan.json')
        if not saved_plan.exists():
            atomic_bytes(saved_plan, canonical(plan))
        if read_json(saved_plan) != plan:
            raise ValueError('retry requires the same plan; use a new job ID')
        candidate = update(plan, market, job, through, report)
        if candidate:
            report['last_success'] = candidate['run']
        report.update(status='success', finished_at=utc_now())
        save_report(job, report)
        if candidate and current != candidate:
            run = candidate['run']
            pending = pending_pointer(pointer_path.parent, run)
            final = guarded(pointer_path.parent/run)
            source = guarded(job/'candidate'/run)
            # Until the marker itself becomes latest, catalog and event readers exclude this run.
            if not pending.exists():
                marker = guarded(job/'pending-pointer.json')
                atomic_bytes(marker, canonical(candidate))
                marker.rename(pending)
            if read_json(pending) != candidate:
                raise ValueError('pending pointer differs from the audited job')
            try:
                if not final.exists():
                    source.rename(final)
                pending.replace(pointer_path)
            except OSError:
                if final.exists() and not source.exists():
                    final.rename(source)
                pending.unlink()
                raise
        return 0
    except Exception as exc:
        report['last_success'] = previous_success
        detail = report['stages'][report['stage']]
        if hasattr(exc, 'profile'):
            detail['profile'] = exc.profile
            dates = exc.profile.get('date_distribution', {})
            if dates and set(dates) != {plan['trade_date']}:
                detail['kind'] = 'stale'
        detail.setdefault('kind', 'missing' if isinstance(exc, FileNotFoundError) else type(exc).__name__)
        detail.update(status='failed', reason=str(exc))
        report.update(status='failed', finished_at=utc_now())
        try:
            save_report(job, report)
        except (OSError, ValueError) as report_error:
            print('Unable to save update report:', report_error, file=sys.stderr)
        return 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--job', required=True, help='Private job ID, reused only with the same plan')
    parser.add_argument('--through', choices=STAGES, default='audit')
    args = parser.parse_args(argv)
    plan = read_json(args.plan)
    if plan.get('market') not in FEEDS or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', args.job):
        parser.error('invalid market or job ID')
    market = guarded(args.root/plan['market'])
    job = guarded(market/'jobs'/args.job)
    job.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_lock(market), exclusive_lock(guarded(market/'runs')):
        code = execute(plan, market, job, args.through)
    print(job/'report.json')
    return code


if __name__ == '__main__':
    raise SystemExit(main())
