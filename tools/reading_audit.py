#!/usr/bin/env python3
"""Summarize source-line coverage separately from reading token expenditure.

Input JSON: {"sources": {"book": {"lines": 1000, "output_budget": 4000}},
"reads": [{"source": "book", "start": 1, "end": 50, "tokens": 600,
"reason": "initial", "question": "", "resolution": ""}]}.
Line coordinates are inclusive original-corpus coordinates local to each source.
Tokens count cleaned input actually read. Coverage counts source spans, not tokens.
"""
import argparse
import json
from pathlib import Path


def summarize(data):
    reports = {}
    for name, source in data['sources'].items():
        if any(type(source.get(k)) is not int or source[k] <= 0 for k in ('lines', 'output_budget')):
            raise ValueError('source lines and output_budget must be positive integers')
        reports[name] = {'unique_lines': 0, 'repeated_lines': 0, 'input_tokens': 0, 'unresolved': [], 'ranges': []}
    for event in data['reads']:
        name = event['source']
        if name not in reports:
            raise ValueError('unknown source: ' + name)
        start, end, tokens = event['start'], event['end'], event['tokens']
        if any(type(x) is not int for x in (start, end, tokens)) or not 1 <= start <= end <= data['sources'][name]['lines'] or tokens < 0:
            raise ValueError('invalid reading span or token count')
        r = reports[name]
        overlap = sum(max(0, min(end, b) - max(start, a) + 1) for a, b in r['ranges'])
        if not event.get('reason') or ((overlap or event['reason'] == 'verification') and not event.get('question')):
            raise ValueError('record a reason for every read and an unresolved question for rereading/verification')
        if event.get('question'):
            question = event['question']
            if event.get('resolution'):
                r['unresolved'] = [q for q in r['unresolved'] if q != question]
            elif question not in r['unresolved']:
                r['unresolved'].append(question)
        r['input_tokens'] += tokens
        r['unique_lines'] += end - start + 1 - overlap
        r['repeated_lines'] += overlap
        merged = []
        for a, b in sorted(r['ranges'] + [[start, end]]):
            if merged and a <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], b)
            else:
                merged.append([a, b])
        r['ranges'] = merged
    for name, r in reports.items():
        source = data['sources'][name]
        r['coverage_fraction'] = r['unique_lines'] / source['lines']
        r['budget_alert'] = r['input_tokens'] > 4 * source['output_budget']
        del r['ranges']
    return reports


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('ledger', type=Path)
    ap.add_argument('--out', type=Path)
    args = ap.parse_args()
    try:
        report = summarize(json.loads(args.ledger.read_text()))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        ap.error(str(exc))
    output = json.dumps(report, indent=2, ensure_ascii=False)
    if args.out:
        args.out.write_text(output + '\n')
    print(output)


if __name__ == '__main__':
    main()
