#!/usr/bin/env python3
"""Validate recorded three-condition behavioral acceptance runs, not model quality itself.

See docs/BEHAVIORAL_ACCEPTANCE.md. No model/API calls or subjective grading happen
here: responses, criterion judgments and retrieval traces must come from actual runs.
"""
import argparse
import hashlib
import json
from pathlib import Path

CONDITIONS = ('baseline', 'core', 'core_references')
KINDS = {'apply', 'inapplicable', 'disagreement', 'unsupported'}


def file_hash(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def runtime_hash(root):
    root = Path(root).resolve()
    files = [root / 'SKILL.md'] + sorted(p for p in (root / 'references').rglob('*') if p.is_file())
    manifest = []
    for p in files:
        if not p.resolve().is_relative_to(root):
            raise ValueError('runtime path escapes skill root')
        manifest.append([p.relative_to(root).as_posix(), file_hash(p)])
    return 'sha256:' + hashlib.sha256(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(suite, results, root, suite_hash, verified_run=None):
    require(suite.get('version') in (1, 2) and suite.get('defined_before_extraction') is True,
            'freeze suite before extraction')
    phase = results.get('phase', 'development')
    require(phase in ('development', 'final'), 'unknown evaluation phase')
    if suite['version'] == 2:
        from evaluation_runner import validate_tasks
        tasks = validate_tasks(suite, phase)
    else:
        require(phase == 'development', 'independent final acceptance needs a version 2 suite')
        tasks = suite['tasks']
    if phase == 'final':
        require(verified_run is not None and results.get('runner_manifest') == verified_run,
                'final acceptance requires verified prediction and grading runs')
    require(isinstance(tasks, list) and len(tasks) >= 4, 'need at least four representative tasks')
    require(len({t['id'] for t in tasks}) == len(tasks), 'duplicate task IDs')
    require(KINDS <= {t['kind'] for t in tasks}, 'cover apply, inapplicable, disagreement and unsupported')
    for t in tasks:
        require(isinstance(t.get('prompt'), str) and t['prompt'].strip(), 'task prompt required')
        require(isinstance(t.get('criteria'), dict) and t['criteria'] and all(isinstance(v, str) and v.strip() for v in t['criteria'].values()), 'named success criteria required')
        require(type(t.get('references_required')) is bool, 'declare whether each task needs references')
    require(any(t['references_required'] for t in tasks),
            'need at least one reference-dependent task to exercise loading')
    require(results['suite_hash'] == suite_hash, 'suite hash stale')
    require(results['content_hash'] == runtime_hash(root), 'runtime hash stale')
    require(all(isinstance(results.get(k), str) and results[k].strip() for k in ('model', 'settings', 'baseline_prompt')), 'record shared model/settings and baseline role prompt')
    runs = results['runs']
    conditions = CONDITIONS + (('core_targeted',) if 'core_targeted' in runs else ())
    require(set(runs) == set(conditions), 'need baseline, core and core_references conditions')
    if 'core_targeted' in runs:
        require(any(t.get('qualification_criteria') for t in tasks), 'targeted experiment needs explicit qualification criteria')
        require(all(set(t.get('qualification_criteria', [])) <= set(t['criteria']) for t in tasks), 'unknown qualification criterion')
    totals, per_task = {}, {}
    for condition in conditions:
        rows = runs[condition]
        require(len(rows) == len(tasks) and len({r['id'] for r in rows}) == len(rows), 'exactly one result per task and condition required')
        by_id = {r['id']: r for r in rows}
        require(set(by_id) == {t['id'] for t in tasks}, 'run task IDs differ from suite')
        totals[condition] = 0
        for task in tasks:
            r = by_id[task['id']]
            require(r.get('fresh_context') is True and isinstance(r.get('answer'), str) and r['answer'].strip(), 'record actual answer from fresh context')
            require(set(r['criteria']) == set(task['criteria']), 'grade every frozen criterion')
            require(all(type(v) is bool for v in r['criteria'].values()), 'criterion grades must be booleans')
            require(isinstance(r.get('rationale'), str) and r['rationale'].strip(), 'grading rationale required')
            loaded = r['references_loaded']
            require(isinstance(loaded, list) and all(isinstance(p, str) for p in loaded), 'record retrieval trace as relative paths')
            if condition not in ('core_references', 'core_targeted'):
                require(not loaded, 'baseline/core condition cannot load references')
            else:
                for path in loaded:
                    candidate = (Path(root) / path).resolve()
                    require(candidate.is_relative_to((Path(root) / 'references').resolve()) and candidate.is_file(), 'invalid retrieved reference: ' + path)
                require(not task['references_required'] or loaded, 'required references did not load')
            value = sum(r['criteria'].values())
            totals[condition] += value
            per_task.setdefault(task['id'], {})[condition] = value
    full_pass = all(all(r['criteria'].values()) for r in runs['core_references'])
    regressions = [pid for pid, scores in per_task.items() if scores['core_references'] < scores['baseline']]
    experiment = {}
    for condition in ('core_references', 'core_targeted'):
        if condition not in runs:
            continue
        rows_by_id = {r['id']: r for r in runs[condition]}
        usages = [u for r in runs[condition] for u in r.get('usage', [])]
        provider_tokens = sum(u['total_tokens'] for u in usages) if usages and all(isinstance(u, dict) and type(u.get('total_tokens')) is int for u in usages) else None
        experiment[condition] = {'score': totals[condition], 'all_criteria_passed': all(all(r['criteria'].values()) for r in runs[condition]), 'provider_total_tokens': provider_tokens,
            'retrieved_characters': sum(e['characters'] for r in runs[condition] for e in r.get('retrievals', [])),
            'missed_qualifications': sum(not rows_by_id[t['id']]['criteria'][key] for t in tasks for key in t.get('qualification_criteria', []))}
    return {'phase': phase, 'independent_final': phase == 'final', 'retrieval_experiment': experiment,
            'passed': full_pass and not regressions, 'totals': totals, 'per_task': per_task,
            'regressions': regressions,
            'core_gain': totals['core'] - totals['baseline'],
            'reference_gain': totals['core_references'] - totals['core'],
            'note': 'A tie does not demonstrate added value. Grades and isolation are recorded evidence, not independently proven by this checker.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('skill_root', type=Path)
    ap.add_argument('--suite', type=Path)
    ap.add_argument('--results', type=Path)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--print-hash', action='store_true')
    ap.add_argument('--prediction-run', type=Path)
    ap.add_argument('--grade-run', type=Path)
    args = ap.parse_args()
    try:
        if args.print_hash:
            print(runtime_hash(args.skill_root))
            return 0
        verified = None
        if args.prediction_run or args.grade_run:
            if not args.prediction_run or not args.grade_run or args.results:
                ap.error('supply both --prediction-run and --grade-run, without --results')
            from evaluation_runner import export_books, verify
            results = export_books(args.prediction_run, args.grade_run)
            verified = verify(args.prediction_run)
        else:
            if not args.results:
                ap.error('--results or verified runner paths required')
            results = json.loads(args.results.read_text())
        if not args.suite:
            ap.error('--suite required')
        report = validate(json.loads(args.suite.read_text()), results, args.skill_root, file_hash(args.suite), verified)
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as exc:
        report = {'passed': False, 'error': str(exc)}
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
