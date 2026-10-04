"""Append time-stamped evidence and mark only explicitly verified checklist items."""
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import argparse,re
ROOT=Path(__file__).resolve().parents[1]
DOC=ROOT/'temp/workdoc_Oct04-2026_articulated_filterreg.md'
def record(message:str,step:int|None=None,items:tuple[int,...]=()):
    content=DOC.read_text()
    if step is not None:
        pattern=rf'(### 手順 {step}:.*?)(?=\n### 手順|\n## |\Z)'
        match=re.search(pattern,content,re.S)
        if not match: raise ValueError(f'Step {step} missing')
        section=match.group(1);i=0;out=[]
        for line in section.splitlines():
            if line.startswith('- ['):
                if i in items: line=line.replace('- [ ]','- [x]',1)
                i+=1
            out.append(line)
        content=content[:match.start()]+ '\n'.join(out)+'\n'+content[match.end():]
    stamp=datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')
    content+=f'\n### 記録 {stamp}\n{message}\n'
    DOC.write_text(content)
    with (ROOT/'logs/journal.jsonl').open('a') as f:
        import json
        f.write(json.dumps({'time':stamp,'step':step,'items':items,'message':message},ensure_ascii=False)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('message');p.add_argument('--step',type=int);p.add_argument('--items',default='')
    a=p.parse_args();record(a.message,a.step,tuple(int(x) for x in a.items.split(',') if x))
