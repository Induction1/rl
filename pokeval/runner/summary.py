#!/usr/bin/env python3
import json
import sys
from collections import Counter


def summarize(path):
    turns = sessions = text_len = 0
    tools = Counter()
    for line in open(path):
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get('type') == 'result':
            sessions += 1
        msg = ev.get('message')
        content = msg.get('content') if isinstance(msg, dict) else None
        if ev.get('type') != 'assistant' or not isinstance(content, list):
            continue
        turns += 1
        for block in content:
            if block.get('type') == 'tool_use':
                tools[block.get('name')] += 1
            elif block.get('type') == 'text':
                text_len += len(block.get('text', ''))
    print(f'transcript: {turns} assistant turns, {sum(tools.values())} tool calls, {sessions} sessions, '
          f'{text_len} chars of text')
    print('tools: ' + ', '.join(f'{k} {v}' for k, v in tools.most_common()))


if __name__ == '__main__':
    summarize(sys.argv[1])
