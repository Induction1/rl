"""Step-100 style failure read: per-question solve rates across evals, the zero set classified by first-sample error, tables/tiers of the zero set."""
import json, re, collections, glob
import sys
# usage: python analysis/read_failures_run2.py <rollouts_dir>   (the run's rollouts/ folder with step_N/eval/all/traces.jsonl)
R=sys.argv[1].rstrip('/')
def load(step, cond='bird-dev-nohint'):
    out=collections.defaultdict(list)
    for l in open(f'{R}/step_{step}/eval/all/traces.jsonl'):
        r=json.loads(l)
        if r['env']['name']!=cond: continue
        t=r['traces'][0]; d=t['task']['data']
        out[d['name']].append(dict(q=d['prompt'].split('Question:')[-1].split('\n')[0].strip()[:110], gold=d['info']['gold_sql'], pred=t['info']['pred_sql'], err=t['info']['error'], ok=t['info']['correct'], tier=d['info']['tier']))
    return out
steps=sorted(int(p.split('step_')[1].split('/')[0]) for p in glob.glob(R+'/step_*/eval/all/traces.jsonl'))
print('eval steps', steps)
S={s:load(s) for s in steps}
names=sorted(S[steps[-1]])
rate={n:{s:sum(x['ok'] for x in S[s][n])/len(S[s][n]) for s in steps if n in S[s]} for n in names}
last=steps[-1]
solid=[n for n in names if rate[n][last]==1]; never=[n for n in names if rate[n][last]==0]; partial=[n for n in names if 0<rate[n][last]<1]
print(f'step {last}: solid 4/4 = {len(solid)}, partial = {len(partial)}, zero 0/4 = {len(never)}')
never_all=[n for n in never if all(rate[n].get(s,0)==0 for s in steps if s>=25)]
print('zero at every eval since 25:', len(never_all))
# what the partials look like: mean rate
print('partial mean rate %.2f'%(sum(rate[n][last] for n in partial)/max(1,len(partial))))
# classify the zero-at-100 questions by first sample
def needsA(s): return bool(re.search(r'\bA\d+\b', s))
cat=collections.Counter(); rows=[]
for n in never:
    x=S[last][n][0]
    if x['err']: c='exec_error'
    elif needsA(x['gold']) and not needsA(x['pred'] or ''): c='missing_Acode'
    else: c='wrong_valid'
    cat[c]+=1; rows.append((c,n,x))
print('zero-at-100 by class:', dict(cat))
errs=collections.Counter(re.sub(r'(no such column|no such table|ambiguous column name): .*', r'\1', x['err']) for _,_,x in rows if x['err'])
print('exec error kinds:', errs.most_common(6))
tabs=lambda s: sorted(set(t.lower() for t in re.findall(r'(?:FROM|JOIN)\s+`?"?(\w+)', s, re.I)))
print('tables in gold of the zero set:', collections.Counter(t for _,_,x in rows for t in tabs(x['gold'])).most_common())
print('tiers of zero set:', collections.Counter(x['tier'] for _,_,x in rows))
print()
for c,n,x in rows[:40]:
    print(f'--- {n} [{c}] t{x["tier"]} rates:', ' '.join(f'{s}:{rate[n].get(s,0):.2f}' for s in steps))
    print('Q:', x['q']); print('G:', x['gold'][:230]); print('P:', (x['pred'] or '')[:230]); 
    if x['err']: print('E:', x['err'][:100])
