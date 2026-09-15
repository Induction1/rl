#!/usr/bin/env python3
import json
import sys

CLIP = 1500


def clip(text):
    text = text.strip()
    return text if len(text) <= CLIP else text[:CLIP] + f'\n… [{len(text) - CLIP} more chars]'


def blocks(ev):
    content = ev.get('message', {}).get('content')
    return content if isinstance(content, list) else []


def render(path):
    out, turn = [], 0
    for line in open(path):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = ev.get('type')
        if kind == 'assistant':
            turn += 1
            for b in blocks(ev):
                if b.get('type') == 'text' and b['text'].strip():
                    out.append(f'\n### turn {turn}\n\n{b["text"].strip()}\n')
                elif b.get('type') == 'tool_use':
                    cmd = b.get('input', {}).get('command') or json.dumps(b.get('input'))
                    out.append(f'\n**run** `{b.get("name")}`\n\n```\n{clip(cmd)}\n```\n')
        elif kind == 'user':
            for b in blocks(ev):
                if b.get('type') == 'tool_result':
                    body = b.get('content')
                    if isinstance(body, list):
                        body = '\n'.join(x.get('text', '') for x in body if isinstance(x, dict))
                    out.append(f'\n<details><summary>result</summary>\n\n```\n{clip(str(body))}\n```\n</details>\n')
        elif kind == 'result':
            out.append(f'\n---\n\nfinished: {ev.get("num_turns")} turns, {ev.get("duration_ms", 0) // 1000} s, '
                       f'cost ${ev.get("total_cost_usd", 0):.2f}\n')
    return ''.join(out)


if __name__ == '__main__':
    sys.stdout.write(render(sys.argv[1]))
