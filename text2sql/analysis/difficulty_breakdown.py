"""Test accuracy by BIRD difficulty label at every eval step, both hint conditions. Usage: python analysis/difficulty_breakdown.py <rollouts_dir>"""
import json, glob, collections, sys
R=sys.argv[1].rstrip('/')
steps=sorted(int(p.split('step_')[1].split('/')[0]) for p in glob.glob(f'{R}/step_*/eval/all/traces.jsonl'))
print('step  simple moderate challenging | with hints')
for s in steps:
    acc={}
    for cond in ['bird-dev-nohint','bird-dev-hint']:
        c=collections.defaultdict(list)
        for l in open(f'{R}/step_{s}/eval/all/traces.jsonl'):
            r=json.loads(l)
            if r['env']['name']!=cond: continue
            t=r['traces'][0]; c[t['task']['data']['info']['tier']].append(t['info']['correct'])
        acc[cond]={k:100*sum(v)/len(v) for k,v in c.items()}
    a,h=acc['bird-dev-nohint'],acc['bird-dev-hint']
    print(f"{s:4d}  {a.get(1,0):5.1f} {a.get(2,0):7.1f} {a.get(4,0):10.1f}   | {h.get(1,0):5.1f} {h.get(2,0):5.1f} {h.get(4,0):5.1f}")
