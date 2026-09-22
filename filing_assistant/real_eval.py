"""Frozen real-source evaluation; exact gold coverage is not semantic truth."""
import hashlib
import importlib.util
import json
from pathlib import Path
from .engine import Scope
from .research import ResearchEngine

ROOT=Path(__file__).resolve().parents[1]

def check_freeze():
    frozen=json.loads((ROOT/'evaluation/real/frozen.json').read_text())
    for f,digest in frozen['files'].items():
        if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen input changed: '+f)

def evaluate(split='dev',methods=('baseline','bm25','semantic','hybrid')):
    check_freeze()
    if split not in {'dev','heldout','dev-v2','heldout-v2'}:raise ValueError('Unknown split')
    versioned=split.endswith('-v2')
    source_split=split[:-3] if versioned else split
    if split in {'heldout','heldout-v2'}:
        selection_name='selection-v2.json' if versioned else 'selection.json'
        selection=json.loads((ROOT/'evaluation/real'/selection_name).read_text())
        for f,digest in selection['implementation'].items():
            if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=digest:raise ValueError('Selected implementation changed: '+f)
    index=json.loads((ROOT/'corpora/sec/data/index.json').read_text())
    rows=[json.loads(s) for s in (ROOT/('evaluation/real/'+source_split+'.jsonl')).read_text().splitlines()]
    spec=importlib.util.spec_from_file_location('baseline',ROOT/'baselines/v1_engine.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    reports={}
    for method in methods:
        engine=module.Engine(index) if method=='baseline' else ResearchEngine(index,ROOT/'corpora/sec/data/semantic.json.gz',method)
        counts=dict(questions=len(rows),answerable=0,unsupported=0,retrieval_complete=0,gold_answer_complete=0,unsupported_abstained=0,false_abstentions=0,incorrect_answers=0,answered=0,exact_excerpts=0,excerpts=0,wrong_scope=0,comparisons=0,complete_comparisons=0)
        results=[]
        for row in rows:
            result=engine.ask(row['question'],Scope(**row['scope']),row['compare'])
            gold={g['passage_id'] for g in row['gold']};retrieved={r['passage_id'] for r in result['retrieved']};cited={a['citation']['passage_id'] for a in result['answer']}
            correct=row['answerable'] and gold<=cited
            counts['answerable']+=row['answerable'];counts['unsupported']+=not row['answerable']
            counts['retrieval_complete']+=bool(gold and gold<=retrieved)
            counts['gold_answer_complete']+=correct
            counts['unsupported_abstained']+=not row['answerable'] and result['status']=='abstained'
            counts['false_abstentions']+=row['answerable'] and result['status']=='abstained'
            counts['incorrect_answers']+=result['status']=='answered' and not correct
            counts['answered']+=result['status']=='answered'
            counts['comparisons']+=row['compare'];counts['complete_comparisons']+=row['compare'] and correct
            for a in result['answer']:
                source=next(p for p in index['passages'] if p['passage_id']==a['citation']['passage_id'])
                counts['excerpts']+=1;counts['exact_excerpts']+=a['excerpt']==source['text']
                counts['wrong_scope']+=source['accession'] not in row['scope']['accessions'] or source['ticker']!=row['scope']['company']
            outcome='correct_abstention' if not row['answerable'] and result['status']=='abstained' else 'gold_complete' if correct else 'false_abstention' if result['status']=='abstained' else 'answer_not_gold_complete'
            results.append(dict(id=row['id'],question=row['question'],answerable=row['answerable'],outcome=outcome,gold=sorted(gold),result=result))
        reports[method]=dict(counts=counts,results=results)
    payload=dict(split=split,human_semantic_support=None,metric_note='Gold-ID completeness is strict: alternate relevant passages count as misses. Incorrect answers includes these gold mismatches; requires independent review.',reports=reports)
    (ROOT/('evaluation/real/'+split+'-results.json')).write_text(json.dumps(payload,indent=2)+'\n')
    return {method:report['counts'] for method,report in reports.items()}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('split',choices=['dev','heldout','dev-v2','heldout-v2']);args=p.parse_args()
    print(json.dumps(evaluate(args.split),indent=2))
