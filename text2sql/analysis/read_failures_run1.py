"""Run 1 failure read (the analysis behind the post mortem table). Usage:
  python analysis/read_failures_run1.py <rollouts_dir> <db_path>
rollouts_dir holds step_N/eval/all/traces.jsonl (prime-rl eval traces); db_path is financial_work.sqlite.
Prints: per-question stability across evals from step 50 on, the step-250 failures by class, gold reachability under
the verifier's row cap, join depth of never vs always solved, and the disjoint/near-miss split of wrong answers."""
import json, re, glob, collections, sys, importlib.util
from pathlib import Path
R=sys.argv[1].rstrip('/'); DB=sys.argv[2]
verify=importlib.util.module_from_spec(spec:=importlib.util.spec_from_file_location('verify', Path(__file__).resolve().parent.parent/'text2sql'/'verify.py')); spec.loader.exec_module(verify)
steps=sorted(int(p.split('step_')[1].split('/')[0]) for p in glob.glob(f'{R}/step_*/eval/all/traces.jsonl'))
def load(step, cond='bird-dev-nohint'):
    out={}
    for l in open(f'{R}/step_{step}/eval/all/traces.jsonl'):
        r=json.loads(l)
        if r['env']['name']!=cond: continue
        t=r['traces'][0]; d=t['task']['data']
        out[d['name']]=dict(q=d['prompt'].split('Question:')[-1].strip()[:200], gold=d['info']['gold_sql'], pred=t['info']['pred_sql'], err=t['info']['error'], ok=t['info']['correct'], tier=d['info']['tier'], exe=t['metrics']['executed'])
    return out
noh={s:load(s) for s in steps}; hint={s:load(s,'bird-dev-hint') for s in steps}; names=sorted(noh[steps[-1]]); late=[s for s in steps if s>=50]
print('evals:',steps,'| questions:',len(names))
print('no-hint: #late evals correct per question:',sorted(collections.Counter(sum(noh[s][n]['ok'] for s in late) for n in names).items()))
never=[n for n in names if all(noh[s][n]['ok']==0 for s in late)]
print('never solved (late evals):',len(never),'| of those solved with hints in 2+ evals:',sum(1 for n in never if sum(hint[s][n]['ok'] for s in late)>=2))
last=steps[-1]; cls=collections.Counter()
for n in names:
    r=noh[last][n]
    if r['ok']: continue
    cls['exec_error' if not r['exe'] else ('gold_uses_Acode' if re.search(r'\bA\d+\b',r['gold']) else 'valid_wrong')]+=1
print(f'step {last} failures by class:',dict(cls))
unwin=collections.Counter()
for n in names:
    g,err=verify.execute(DB,noh[last][n]['gold']); unwin['error' if err else 'empty' if not g else 'gt1000' if len(g)>1000 else 'ok']+=1
print('gold reachability under the row cap:',dict(unwin))
ntab=lambda s: len(set(re.findall(r'(?:FROM|JOIN)\s+`?(\w+)`?',s,re.I)))
b=collections.defaultdict(list)
for n in names:
    k=sum(noh[s][n]['ok'] for s in late); b['never' if k==0 else 'always' if k==len(late) else 'flip'].append(ntab(noh[last][n]['gold']))
for k,v in b.items(): print(f'{k}: n={len(v)} mean tables in gold {sum(v)/len(v):.2f}')
kinds=collections.Counter()
for n in names:
    r=noh[last][n]
    if r['ok'] or not r['pred'] or r['err']: continue
    p,_=verify.execute(DB,r['pred']); g,_=verify.execute(DB,r['gold'])
    if not p: kinds['pred_empty']+=1
    elif len(p[0])!=len(g[0]): kinds['column_count']+=1
    else:
        sp,sg=set(verify._rows(p)),set(verify._rows(g)); kinds['disjoint' if not sp&sg else 'overlap']+=1
print('wrong-but-valid answers:',dict(kinds))
