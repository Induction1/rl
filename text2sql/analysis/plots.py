"""Figures for the writeup: run 1 test accuracy, run 1 training pool vs test, run 1 by BIRD difficulty, hint lift, run 2 checkpoint sweep, run 2 pool vs test. Light and dark variants."""
import json, glob, collections, numpy as np, matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
import os, sys
# usage: python analysis/plots.py <runs_dir> <out_dir>   (runs_dir holds t2s-v1/metrics.jsonl, t2s-v2/metrics.jsonl, ckpt_eval/summary.json, t2s-v1/rollouts/)
R=sys.argv[1].rstrip('/')+'/'; OUT=sys.argv[2].rstrip('/')+'/'; os.makedirs(OUT,exist_ok=True)
r1=[json.loads(l) for l in open(R+'t2s-v1/metrics.jsonl')]; r2=[json.loads(l) for l in open(R+'t2s-v2/metrics.jsonl')]
S=json.load(open(R+'ckpt_eval/summary.json')); order=['base']+[f'step_{i}' for i in range(25,251,25)]; steps=[0 if c=='base' else int(c.split('_')[1]) for c in order]
def curve(rows,key):
    out=[(r['step'],100*r[key]) for r in rows if key in r and r.get('step') is not None]; return [a for a,_ in out],[b for _,b in out]
def train_curve(rows):
    last={}
    for r in rows:
        if r.get('step') is not None and 'train/text2sql/all/agent/rewards/correct/mean' in r: last[int(r['step'])]=100*r['train/text2sql/all/agent/rewards/correct/mean']
    st=np.array(sorted(last)); tv=np.array([last[k] for k in st]); w=10; return st,tv,st[w-1:],np.convolve(tv,np.ones(w)/w,mode='valid')
# difficulty breakdown, run 1
dsteps=sorted(int(p.split('step_')[1].split('/')[0]) for p in glob.glob(R+'t2s-v1/rollouts/step_*/eval/all/traces.jsonl'))
acc={c:{k:[] for k in (1,2,4)} for c in ['bird-dev-nohint','bird-dev-hint']}
for s_ in dsteps:
    for cond in acc:
        c=collections.defaultdict(list)
        for l in open(R+f't2s-v1/rollouts/step_{s_}/eval/all/traces.jsonl'):
            r=json.loads(l)
            if r['env']['name']!=cond: continue
            t=r['traces'][0]; c[t['task']['data']['info']['tier']].append(t['info']['correct'])
        for k in (1,2,4): acc[cond][k].append(100*sum(c[k])/len(c[k]))
MUSTARD='#e0a63a'; MAUVE='#a95c7a'; INDIGO='#5b4fcf'; TERRA='#c96a4a'; TEAL='#3f8f8a'
def theme(dark):
    global INK,SUB,GRID,SPINE,BASE,IND,MAU
    if dark: INK='#e6e6e6'; SUB='#a8a8a8'; GRID='#3a3a3a'; SPINE='#555'; BASE='#777'; IND='#8f85e8'; MAU='#c97a9a'
    else: INK='#2b2b2b'; SUB='#6f6f6f'; GRID='#ececec'; SPINE='#d9d9d9'; BASE='#b8b8b8'; IND=INDIGO; MAU=MAUVE
    plt.rcParams.update({'font.family':['Helvetica Neue','Helvetica','Arial','DejaVu Sans'],'font.size':11,'text.color':INK,'axes.labelcolor':SUB,'xtick.color':SUB,'ytick.color':SUB})
def card(fig,ax):
    fig.patch.set_alpha(0); ax.set_facecolor('none')
    for sp in ['top','right']: ax.spines[sp].set_visible(False)
    for sp in ['left','bottom']: ax.spines[sp].set_color(SPINE)
    ax.yaxis.grid(True,color=GRID,lw=0.9); ax.set_axisbelow(True); ax.tick_params(length=0)
def axes_pct(ax,ymax,xmax=250):
    ax.set_xlim(-4,xmax+3); ax.set_ylim(0,ymax); ax.set_xticks(range(0,xmax+1,50)); yt=list(range(0,ymax+1,20)); ax.set_yticks(yt); ax.set_yticklabels([f'{y}%' for y in yt]); ax.set_xlabel('training step')
def save(fig,name,dark): fig.savefig(OUT+name+('_dark' if dark else '')+'.png',transparent=True); plt.close(fig)
for dark in (False,True):
    theme(dark)
    # 1 run1 held out
    fig,ax=plt.subplots(figsize=(8.6,4.4),dpi=170); card(fig,ax)
    for y,lab in [(78,'Sonnet 5 zero shot, with hints'),(53,'Sonnet 5 zero shot, no hints')]:
        ax.axhline(y,color=BASE,lw=1,ls=(0,(3,3))); ax.text(248,y+1.6,lab,color=SUB,fontsize=9.5,ha='right',va='bottom')
    for key,lab,c,lx,ly in [('eval/bird-dev-hint/all/agent/rewards/correct/mean','with hints',TERRA,128,50.5),('eval/bird-dev-nohint/all/agent/rewards/correct/mean','no hints',IND,128,28.5)]:
        x,y=curve(r1,key); ax.plot(x,y,color=c,lw=2.6,marker='o',ms=4.2,mfc=c,mec='none'); ax.text(lx,ly,lab,color=c,fontsize=11.5,va='center')
    axes_pct(ax,90); ax.set_yticks(range(0,81,20)); ax.set_yticklabels([f'{y}%' for y in range(0,81,20)]); fig.subplots_adjust(left=0.075,right=0.97,top=0.95,bottom=0.15); save(fig,'run1_heldout',dark)
    # 2 run1 training vs held out
    st,tv,ss,sm=train_curve(r1)
    fig,ax=plt.subplots(figsize=(8.6,4.3),dpi=170); card(fig,ax)
    ax.plot(st,tv,color=MUSTARD,lw=0.8,alpha=0.3); ax.plot(ss,sm,color=MUSTARD,lw=2.8,label='training pool, 10 step average')
    for key,lab,c in [('eval/bird-dev-hint/all/agent/rewards/correct/mean','test set, with hints',TERRA),('eval/bird-dev-nohint/all/agent/rewards/correct/mean','test set, no hints',IND)]:
        x,y=curve(r1,key); ax.plot(x,y,color=c,lw=1.8,marker='o',ms=3.5,mfc=c,mec='none',alpha=0.5,label=lab)
    ax.legend(loc='upper left',frameon=False,fontsize=10,handlelength=2.2,labelcolor='linecolor'); axes_pct(ax,100); fig.subplots_adjust(left=0.075,right=0.97,top=0.95,bottom=0.15); save(fig,'run1_training',dark)
    # 3 run1 difficulty, two panels
    fig,axes=plt.subplots(1,2,figsize=(9.4,3.9),dpi=170,sharey=True); fig.patch.set_alpha(0)
    for ax,cond,ttl in zip(axes,['bird-dev-nohint','bird-dev-hint'],['no hints','with hints']):
        card(fig,ax)
        for k,lab,c in [(1,'simple (62)',MUSTARD),(2,'moderate (37)',MAU),(4,'challenging (7)',IND)]:
            y=acc[cond][k]; ax.plot(dsteps,y,color=c,lw=2.4,marker='o',ms=3.8,mfc=c,mec='none'); ax.text(253,y[-1]+(2 if k==1 else -2 if k==2 else 1.5),lab,color=c,fontsize=10,ha='left',va='center')
        ax.set_xlim(-4,253); ax.set_ylim(0,65); ax.set_xticks(range(0,251,50)); ax.set_xlabel('training step'); ax.set_title(ttl,fontsize=11.5,color=INK,loc='left',pad=6)
    axes[0].set_yticks(range(0,61,20)); axes[0].set_yticklabels([f'{y}%' for y in range(0,61,20)])
    fig.subplots_adjust(left=0.06,right=0.86,top=0.9,bottom=0.16,wspace=0.42); save(fig,'run1_difficulty',dark)
    # 4 hint lift at step 250, grouped bars
    fig,ax=plt.subplots(figsize=(6.2,3.6),dpi=170); card(fig,ax)
    labs=['simple (62)','moderate (37)','challenging (7)']; nh=[acc['bird-dev-nohint'][k][-1] for k in (1,2,4)]; wh=[acc['bird-dev-hint'][k][-1] for k in (1,2,4)]
    x=np.arange(3); ax.bar(x-0.19,nh,0.36,color=IND,label='no hints'); ax.bar(x+0.19,wh,0.36,color=TERRA,label='with hints')
    for i,(a,b) in enumerate(zip(nh,wh)): ax.text(i-0.19,a+1.5,f'{a:.0f}',ha='center',fontsize=10,color=IND); ax.text(i+0.19,b+1.5,f'{b:.0f}',ha='center',fontsize=10,color=TERRA)
    ax.set_xticks(x); ax.set_xticklabels(labs); ax.set_ylim(0,65); ax.set_yticks(range(0,61,20)); ax.set_yticklabels([f'{y}%' for y in range(0,61,20)]); ax.legend(frameon=False,fontsize=10,labelcolor='linecolor',loc='upper right')
    fig.subplots_adjust(left=0.1,right=0.97,top=0.95,bottom=0.14); save(fig,'run1_hintlift',dark)
    # 5 run2 held out sweep
    fig,ax=plt.subplots(figsize=(8.6,4.6),dpi=170); card(fig,ax)
    x,y=curve(r1,'eval/bird-dev-nohint/all/agent/rewards/correct/mean'); ax.plot(x,y,color=IND,lw=1.4,ls=(0,(3,3)),alpha=0.55); ax.text(256,y[-1],'run 1, no hints',color=IND,alpha=0.75,fontsize=10,ha='left',va='center')
    ends={}
    for sname,c in [('wretblad',TEAL),('orig_hint',TERRA),('orig_nohint',IND)]:
        yy=[100*S[c_][sname]['ex'] for c_ in order]; ax.plot(steps,yy,color=c,lw=2.6,marker='o',ms=4.2,mfc=c,mec='none'); ends[sname]=yy[-1]
    for sname,lab,c,yy in [('wretblad','corrected 106',TEAL,ends['wretblad']+0.5),('orig_hint','with hints',TERRA,ends['orig_hint']+2.2),('orig_nohint','no hints',IND,ends['orig_nohint']-2.2)]:
        ax.text(256,yy,lab,color=c,fontsize=11,ha='left',va='center')
    axes_pct(ax,80); fig.subplots_adjust(left=0.075,right=0.84,top=0.95,bottom=0.15); save(fig,'run2_heldout',dark)
    # 6 run2 training vs held out
    st,tv,ss,sm=train_curve(r2)
    fig,ax=plt.subplots(figsize=(8.6,4.3),dpi=170); card(fig,ax)
    ax.plot(st,tv,color=MUSTARD,lw=0.8,alpha=0.3); ax.plot(ss,sm,color=MUSTARD,lw=2.8,label='training pool, 10 step average')
    ax.plot(steps,[100*S[c]['orig_nohint']['ex'] for c in order],color=IND,lw=1.8,marker='o',ms=3.5,mfc=IND,mec='none',alpha=0.55,label='test set, no hints')
    ax.legend(loc='lower right',frameon=False,fontsize=10,handlelength=2.2,labelcolor='linecolor'); axes_pct(ax,100); fig.subplots_adjust(left=0.075,right=0.97,top=0.95,bottom=0.15); save(fig,'run2_transfer',dark)
print('12 figures saved')
