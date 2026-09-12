#!/usr/bin/env python3
"""Optional stateless HTTP evaluation runner. Prediction, grading and review are separate runs.

Uses a user-selected chat-completions-compatible HTTP endpoint. The model can ask
only for allowlisted reference text via a JSON read action. It receives no shell,
filesystem tool, grading key or history from another task. Records are write-once
and hash-sealed (tamper-evident, not protection against the machine's owner).
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import urllib.request
from urllib.parse import urlsplit

VERSION = 1


def dumps(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n'


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def write_once(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as out:
        out.write(dumps(data))
    path.chmod(0o444)


def seal(root):
    files = {p.relative_to(root).as_posix(): digest(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file()}
    write_once(root / 'manifest.json', {'version': VERSION, 'files': files})


def verify(root):
    root = Path(root)
    manifest = json.loads((root / 'manifest.json').read_text())
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.relative_to(root).as_posix() != 'manifest.json'}
    require(actual == set(manifest['files']), 'run file inventory changed')
    for rel, expected in manifest['files'].items():
        p = (root / rel).resolve()
        require(p.is_relative_to(root.resolve()) and p.is_file(), 'run path escapes sealed directory')
        require(digest(p.read_bytes()) == expected, 'run record changed: ' + rel)
    return digest((root / 'manifest.json').read_bytes())


def snapshot(skill_root):
    root = Path(skill_root).resolve()
    files = [root / 'SKILL.md'] + sorted(p for p in (root / 'references').rglob('*') if p.is_file())
    contents, manifest = {}, []
    for p in files:
        require(p.resolve().is_relative_to(root), 'runtime file escapes skill root')
        rel = p.relative_to(root).as_posix()
        raw = p.read_bytes()
        manifest.append([rel, digest(raw)])
        if p.suffix.lower() in ('.md', '.json'):
            contents[rel] = raw.decode('utf-8')
    content_hash = digest(json.dumps(manifest, ensure_ascii=False, separators=(',', ':')).encode())
    return contents, content_hash


def section_index(contents):
    """Address H2/H3 sections in canonical books, bundling global decision guards."""
    result = {}
    for path, text in contents.items():
        if not path.startswith('references/') or not path.endswith('.md'):
            continue
        lines = text.splitlines(keepends=True)
        headings = []
        fence = False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(('```', '~~~')):
                fence = not fence
            match = re.match(r'^(#{2,3})\s+(.+)', line) if not fence else None
            if match:
                headings.append((i, len(match[1]), match[2].strip()))
        for i, level, title in headings:
            end = next((j for j, depth, _ in headings if j > i and depth <= level), len(lines))
            key = path + '#L' + str(i + 1)
            result[key] = {'path': path, 'title': title, 'start': i + 1, 'end': end,
                           'text': ''.join(lines[i:end]), 'source_hash': digest(text.encode()), 'needs': []}
        guards = [k for k, row in result.items() if row['path'] == path and
                  ('decision rules' in row['title'].lower() or 'mental model' in row['title'].lower())]
        for row in result.values():
            if row['path'] == path:
                row['needs'] = [g for g in guards if result[g] is not row]
    return result


def read_reference(path, condition, contents, index):
    if condition in ('baseline', 'core') or condition.startswith('neighbor'):
        raise ValueError('this condition cannot retrieve references')
    if condition == 'core_targeted':
        require(path in index, 'targeted reads require a catalog section ID')
        ids = [path] + index[path]['needs']
        return '\n\n'.join(index[k]['text'] for k in ids), [
            {key: value for key, value in index[k].items() if key not in ('text', 'needs')} for k in ids]
    require(path.startswith('references/') and path in contents, 'reference is not allowlisted')
    require('#' not in path, 'whole-reference condition needs a whole reference path')
    return contents[path], [{'path': path, 'source_hash': digest(contents[path].encode())}]


def validate_endpoint(endpoint):
    parsed = urlsplit(endpoint)
    require(parsed.scheme in ('http', 'https') and not parsed.query and not parsed.username,
            'endpoint must be an HTTP(S) URL without credentials or query secrets')


def http_client(endpoint, model, messages, temperature):
    validate_endpoint(endpoint)
    payload = {'model': model, 'messages': messages, 'temperature': temperature, 'stream': False}
    headers = {'Content-Type': 'application/json'}
    if os.environ.get('EVALUATION_API_KEY'):
        headers['Authorization'] = 'Bearer ' + os.environ['EVALUATION_API_KEY']
    request = urllib.request.Request(endpoint, dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = json.load(response)
    return {'text': raw['choices'][0]['message']['content'], 'usage': raw.get('usage'), 'raw': raw}


def validate_tasks(suite, phase):
    require(suite.get('version') == 2, 'runner needs suite version 2 with development/final partitions')
    require(suite.get('defined_before_extraction') is True, 'suite must be frozen before extraction')
    tasks = suite['tasks']
    require(tasks and len({t['id'] for t in tasks}) == len(tasks), 'task IDs must be unique')
    groups = {}
    for task in tasks:
        require(task['partition'] in ('development', 'final') and task.get('group'), 'every task needs partition and scenario group')
        require(task['group'] not in groups or groups[task['group']] == task['partition'], 'related task group crosses partitions')
        groups[task['group']] = task['partition']
        require(isinstance(task.get('prompt'), str) and task['prompt'].strip(), 'task prompt required')
    chosen = [t for t in tasks if t['partition'] == phase]
    require(chosen, 'selected partition is empty')
    return chosen


def new_run(runs_root, kind):
    root = Path(runs_root) / (kind + '-' + secrets.token_hex(12))
    root.mkdir(parents=True, exist_ok=False)
    return root


def predict(skill_root, suite_path, runs_root, endpoint, model, phase='development', kind='books',
            targeted=False, temperature=0, client=http_client, max_steps=12):
    validate_endpoint(endpoint)
    suite_raw = Path(suite_path).read_bytes()
    suite = json.loads(suite_raw)
    tasks = validate_tasks(suite, phase)
    contents, content_hash = snapshot(skill_root)
    index = section_index(contents)
    if kind == 'books':
        require(any(t.get('references_required') is True for t in tasks), 'selected partition needs a reference-dependent task')
    root = new_run(runs_root, 'predict')
    # Claim before the first model call. Failed final attempts remain exposed.
    if phase == 'final':
        claim_paths = [Path(runs_root) / 'final-claims' / (digest(group.encode()).split(':')[1] + '.json')
                       for group in sorted({t['group'] for t in tasks})]
        if any(p.exists() for p in claim_paths):
            raise FileExistsError('final scenario group already exposed in this registry')
        for claim in claim_paths:
            write_once(claim, {'run': root.name, 'suite_hash': digest(suite_raw), 'task_ids': [t['id'] for t in tasks]})
    conditions = {'baseline': suite['baseline_prompt'], 'core': contents['SKILL.md'],
                  'core_references': contents['SKILL.md']} if kind == 'books' else {
                  'baseline': suite['baseline_prompt'], 'persona': contents['SKILL.md']}
    if targeted:
        require(kind == 'books', 'targeted experiment is a Books condition')
        conditions['core_targeted'] = contents['SKILL.md']
    for neighbor in suite.get('neighbors', []):
        require(kind == 'persona' and re.fullmatch(r'neighbor[0-9]+', neighbor['id']), 'neighbor IDs must be neighbor1, neighbor2, ...')
        conditions[neighbor['id']] = neighbor['prompt']
    config = {'version': VERSION, 'kind': kind, 'phase': phase, 'model': model, 'temperature': temperature,
              'suite_hash': digest(suite_raw), 'content_hash': content_hash, 'endpoint': endpoint,
              'baseline_prompt': suite['baseline_prompt'], 'conditions': list(conditions)}
    write_once(root / 'config.json', config)
    write_once(root / 'runtime-snapshot.json', contents)
    write_once(root / 'task-prompts.json', [{'id': t['id'], 'prompt': t['prompt']} for t in tasks])
    rows = []
    try:
        for task in tasks:
            for condition, system in conditions.items():
                if condition.startswith('neighbor') and task.get('kind') != 'identity':
                    continue
                catalog = ({k: {p: v for p, v in row.items() if p in ('title', 'needs')} for k, row in index.items()}
                           if condition == 'core_targeted' else list(p for p in contents if p.startswith('references/')))
                can_read = condition in ('core_references', 'core_targeted', 'persona')
                instructions = ('\nReturn only JSON: {"action":"answer","text":"..."} or '
                    '{"action":"read","path":"an allowed catalog ID"}. No other tools exist.\n')
                instructions += ('Allowed references: ' + dumps(catalog)) if can_read else 'Reference access is disabled.'
                # Every task/condition starts a new message list; rubric and expected answers are absent.
                messages = [{'role': 'system', 'content': system + instructions}, {'role': 'user', 'content': task['prompt']}]
                if condition == 'persona' and 'references/scope.md' in contents:
                    messages[0]['content'] += '\nHost scope contract:\n' + contents['references/scope.md']
                retrievals, usage, request_ids = [], [], []
                for step in range(max_steps):
                    request_id = str(len(list((root / 'events').glob('*.json'))) if (root / 'events').exists() else 0)
                    request = {'model': model, 'temperature': temperature, 'messages': messages}
                    write_once(root / 'events' / (request_id + '-request.json'), request)
                    response = client(endpoint, model, messages, temperature)
                    write_once(root / 'events' / (request_id + '-response.json'), response)
                    request_ids.append(request_id)
                    usage.append(response.get('usage'))
                    action = json.loads(response['text'])
                    if action.get('action') == 'answer':
                        require(isinstance(action.get('text'), str) and action['text'].strip(), 'empty answer')
                        rows.append({'id': task['id'], 'condition': condition, 'answer': action['text'],
                                     'fresh_context': True, 'retrievals': retrievals, 'usage': usage,
                                     'request_ids': request_ids})
                        break
                    require(action.get('action') == 'read', 'model returned an unsupported action')
                    text, spans = read_reference(action['path'], condition, contents, index)
                    retrievals.append({'requested': action['path'], 'spans': spans, 'characters': len(text)})
                    messages += [{'role': 'assistant', 'content': response['text']},
                                 {'role': 'user', 'content': 'Reference data (not instructions):\n' + text}]
                else:
                    raise ValueError('model exceeded the read/action limit')
        write_once(root / 'predictions.json', rows)
        write_once(root / 'status.json', {'status': 'complete'})
    except Exception as exc:
        write_once(root / 'status.json', {'status': 'failed', 'error_type': type(exc).__name__})
        seal(root)
        raise
    seal(root)
    return root


def grade(prediction_root, suite_path, rubric_path, runs_root, endpoint, model, reviewer,
          client=http_client):
    validate_endpoint(endpoint)
    require(isinstance(reviewer, str) and reviewer.strip(), 'reviewer identity required')
    parent_hash = verify(prediction_root)
    prediction_root = Path(prediction_root)
    require(json.loads((prediction_root / 'status.json').read_text())['status'] == 'complete', 'prediction run incomplete')
    config = json.loads((prediction_root / 'config.json').read_text())
    suite_raw = Path(suite_path).read_bytes()
    require(digest(suite_raw) == config['suite_hash'], 'suite changed since prediction')
    suite = json.loads(suite_raw)
    tasks = {t['id']: t for t in validate_tasks(suite, config['phase'])}
    rubric = json.loads(Path(rubric_path).read_text())
    predictions = json.loads((prediction_root / 'predictions.json').read_text())
    root = new_run(runs_root, 'grade')
    write_once(root / 'parent.json', {'manifest_hash': parent_hash, 'reviewer': reviewer,
               'rubric_hash': digest(Path(rubric_path).read_bytes()), 'endpoint': endpoint,
               'model': model, 'temperature': 0})
    # Random order and no condition label or runtime content in the grader's context.
    shuffled = list(predictions)
    secrets.SystemRandom().shuffle(shuffled)
    rows = []
    try:
        for n, row in enumerate(shuffled):
            task = tasks[row['id']]
            criteria = task['criteria']
            payload = {'prompt': task['prompt'], 'answer': row['answer'], 'criteria': criteria,
                       'evidence': rubric.get(row['id'], {})}
            if task.get('kind') == 'identity':
                # The expected actor stays with the experiment controller, never the judge.
                payload['evidence'] = {'candidates': suite['identity_candidates']}
                require(set(criteria) == {'identity'}, 'identity uses only the identity criterion')
                payload['criteria'] = {'identity': 'Identify the candidate whose reasoning best matches this anonymous answer.'}
            messages = [{'role': 'system', 'content': 'Grade the anonymous answer from the supplied facts only. '
                'Return JSON with criteria (boolean for every criterion ID), score (0/1/2), rationale (string), '
                'disputed (boolean), and for identity choice (one candidate name). Flag ambiguous judgments disputed.'},
                {'role': 'user', 'content': dumps(payload)}]
            write_once(root / 'events' / (str(n) + '-request.json'), {'messages': messages, 'model': model})
            response = client(endpoint, model, messages, 0)
            write_once(root / 'events' / (str(n) + '-response.json'), response)
            value = json.loads(response['text'])
            require(set(value) <= {'criteria', 'score', 'rationale', 'disputed', 'choice'}, 'grader tried to replace prediction metadata')
            require(set(value['criteria']) == set(criteria) and all(type(v) is bool for v in value['criteria'].values()), 'grader criterion keys/types invalid')
            require(type(value['score']) is int and value['score'] in (0, 1, 2) and type(value['disputed']) is bool and isinstance(value.get('rationale'), str) and value['rationale'].strip(), 'grader output invalid')
            if task.get('kind') == 'identity':
                require(value.get('choice') in suite['identity_candidates'], 'identity choice not in candidates')
            rows.append({**row, **value, 'reviewer': reviewer})
        write_once(root / 'grades.json', rows)
        write_once(root / 'status.json', {'status': 'complete'})
    except Exception as exc:
        write_once(root / 'status.json', {'status': 'failed', 'error_type': type(exc).__name__})
        seal(root)
        raise
    seal(root)
    return root


def export_books(prediction_root, grade_root):
    prediction_hash = verify(prediction_root)
    verify(grade_root)
    config = json.loads((Path(prediction_root) / 'config.json').read_text())
    require(json.loads((Path(grade_root) / 'parent.json').read_text())['manifest_hash'] == prediction_hash, 'grades belong to another run')
    rows = json.loads((Path(grade_root) / 'grades.json').read_text())
    require(all(not r['disputed'] for r in rows), 'disputed grades require human review')
    result = {k: config[k] for k in ('suite_hash', 'content_hash', 'model', 'baseline_prompt', 'phase')}
    result.update(settings=dumps({'temperature': config['temperature']}), runner_manifest=prediction_hash, runs={})
    for row in rows:
        loaded = sorted({span['path'] for event in row['retrievals'] for span in event['spans']})
        result['runs'].setdefault(row['condition'], []).append({
            'id': row['id'], 'fresh_context': True, 'answer': row['answer'], 'criteria': row['criteria'],
            'rationale': row['rationale'], 'references_loaded': loaded, 'retrievals': row['retrievals'], 'usage': row['usage']})
    return result


def review(grade_root, corrections_path, runs_root):
    parent_hash = verify(grade_root)
    source = Path(grade_root)
    rows = json.loads((source / 'grades.json').read_text())
    corrections = json.loads(Path(corrections_path).read_text())
    known = {r['id'] + '/' + r['condition'] for r in rows}
    require(set(corrections) <= known and corrections, 'corrections must address existing task/condition IDs')
    for row in rows:
        key = row['id'] + '/' + row['condition']
        if key in corrections:
            change = corrections[key]
            require(change.get('reviewer') and change.get('rationale'), 'human reviewer and rationale required')
            require(set(change['criteria']) == set(row['criteria']) and all(type(v) is bool for v in change['criteria'].values()), 'review criteria invalid')
            require(type(change['score']) is int and change['score'] in (0, 1, 2), 'review score invalid')
            row.update({k: change[k] for k in ('criteria', 'score', 'rationale', 'reviewer')}, disputed=False)
            if 'choice' in change:
                row['choice'] = change['choice']
    root = new_run(runs_root, 'review')
    parent = json.loads((source / 'parent.json').read_text())
    parent.update(reviewed_manifest=parent_hash, corrections_hash=digest(Path(corrections_path).read_bytes()))
    write_once(root / 'parent.json', parent)
    write_once(root / 'corrections.json', corrections)
    write_once(root / 'grades.json', rows)
    write_once(root / 'status.json', {'status': 'complete'})
    seal(root)
    return root


def export_persona(prediction_root, grade_roots, suite_path):
    prediction_hash = verify(prediction_root)
    config = json.loads((Path(prediction_root) / 'config.json').read_text())
    suite_raw = Path(suite_path).read_bytes()
    require(digest(suite_raw) == config['suite_hash'] and config['kind'] == 'persona', 'persona suite does not match prediction run')
    suite = json.loads(suite_raw)
    tasks = {t['id']: t for t in validate_tasks(suite, config['phase'])}
    grade_sets = []
    for root in grade_roots:
        verify(root)
        require(json.loads((Path(root) / 'parent.json').read_text())['manifest_hash'] == prediction_hash, 'grades belong to another prediction run')
        rows = json.loads((Path(root) / 'grades.json').read_text())
        require(all(not r['disputed'] for r in rows), 'disputed judgments require review')
        grade_sets.append({(r['id'], r['condition']): r for r in rows})
    require(grade_sets, 'at least one grade run required')
    primary = grade_sets[0]
    projection = []
    behavior = {'content_hash': config['content_hash'], 'reasoning': [], 'commitment': [], 'scope': [],
                'identity': {'candidates': suite.get('identity_candidates', []), 'cases': []}}
    for task in tasks.values():
        key = (task['id'], 'persona')
        row = primary[key]
        kind = task['kind']
        if kind != 'identity':
            require(all(values[key]['criteria'] == row['criteria'] and values[key]['score'] == row['score'] for values in grade_sets),
                    'reviewers disagree; resolve with append-only human review before export')
        if kind == 'projection':
            baseline_key = (task['id'], 'baseline')
            baseline = primary[baseline_key]
            require(all(values[baseline_key]['criteria'] == baseline['criteria'] and values[baseline_key]['score'] == baseline['score'] for values in grade_sets),
                    'reviewers disagree on baseline; resolve with human review before export')
            projection.append({'id': task['id'], 'prompt': task['prompt'], 'answer': row['answer'],
                               'baseline_answer': baseline['answer'], 'score': row['score'],
                               'baseline_score': baseline['score'], 'rationale': row['rationale']})
        elif kind in ('reasoning', 'commitment', 'scope'):
            behavior[kind].append({**{k: v for k, v in task.items() if k not in ('criteria',)},
                'answer': row['answer'], 'criteria': row['criteria'], 'rationale': row['rationale'], 'disputed': row['disputed']})
        elif kind == 'identity':
            actors = {'persona': suite['subject']}
            actors.update({n['id']: n['name'] for n in suite.get('neighbors', [])})
            for condition, actor in actors.items():
                grades = [values[(task['id'], condition)] for values in grade_sets]
                behavior['identity']['cases'].append({'id': task['id'], 'prompt': task['prompt'],
                    'answer': grades[0]['answer'], 'truth': actor,
                    'judgments': [{'reviewer': r['reviewer'], 'choice': r['choice'], 'rationale': r['rationale'],
                                   'blinded': True, 'disputed': r['disputed']} for r in grades]})
    baseline_votes = [values[(task['id'], 'baseline')]['choice'] == suite['subject']
                      for task in tasks.values() if task['kind'] == 'identity' for values in grade_sets]
    behavior['identity']['baseline_accuracy'] = sum(baseline_votes) / len(baseline_votes) if baseline_votes else None
    result = {'runner_manifest': prediction_hash, 'phase': config['phase'], 'behavioral': behavior}
    if projection:
        n = len(projection)
        result['projection'] = {'content_hash': config['content_hash'], 'items': projection,
            'overall': sum(r['score'] for r in projection) / (2 * n),
            'baseline': sum(r['baseline_score'] for r in projection) / (2 * n),
            'hit_2': sum(r['score'] == 2 for r in projection) / n, 'hit_1': sum(r['score'] == 1 for r in projection) / n,
            'fresh_context': True, 'model': config['model'], 'settings': dumps({'temperature': config['temperature']}),
            'baseline_prompt': config['baseline_prompt']}
        result['projection']['passed'] = result['projection']['overall'] >= .5 and result['projection']['overall'] >= result['projection']['baseline']
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    p = sub.add_parser('predict')
    p.add_argument('skill_root', type=Path)
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--runs-root', type=Path, required=True)
    p.add_argument('--endpoint', required=True)
    p.add_argument('--model', required=True)
    p.add_argument('--phase', choices=('development', 'final'), default='development')
    p.add_argument('--kind', choices=('books', 'persona'), default='books')
    p.add_argument('--targeted', action='store_true')
    p = sub.add_parser('grade')
    p.add_argument('prediction_root', type=Path)
    for key in ('suite', 'rubric', 'runs-root'):
        p.add_argument('--' + key, type=Path, required=True)
    for key in ('endpoint', 'model', 'reviewer'):
        p.add_argument('--' + key, required=True)
    p = sub.add_parser('review')
    p.add_argument('grade_root', type=Path)
    p.add_argument('--corrections', type=Path, required=True)
    p.add_argument('--runs-root', type=Path, required=True)
    p = sub.add_parser('export-books')
    p.add_argument('prediction_root', type=Path)
    p.add_argument('grade_root', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('export-persona')
    p.add_argument('prediction_root', type=Path)
    p.add_argument('--grades', nargs='+', type=Path, required=True)
    p.add_argument('--suite', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('verify')
    p.add_argument('root', type=Path)
    p = sub.add_parser('index')
    p.add_argument('skill_root', type=Path)
    p.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    try:
        if args.command == 'predict':
            print(predict(args.skill_root, args.suite, args.runs_root, args.endpoint, args.model, args.phase, args.kind, args.targeted))
        elif args.command == 'grade':
            print(grade(args.prediction_root, args.suite, args.rubric, args.runs_root, args.endpoint, args.model, args.reviewer))
        elif args.command == 'review':
            print(review(args.grade_root, args.corrections, args.runs_root))
        elif args.command == 'export-books':
            write_once(args.out, export_books(args.prediction_root, args.grade_root))
        elif args.command == 'export-persona':
            write_once(args.out, export_persona(args.prediction_root, args.grades, args.suite))
        elif args.command == 'verify':
            print(verify(args.root))
        else:
            contents, _ = snapshot(args.skill_root)
            write_once(args.out, {k: {p: v for p, v in row.items() if p != 'text'} for k, row in section_index(contents).items()})
    except (ValueError, KeyError, TypeError, OSError) as exc:
        ap.error(str(exc))


if __name__ == '__main__':
    main()
