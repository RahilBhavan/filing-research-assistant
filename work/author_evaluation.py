"""Source-authored labels frozen before retrieval development. Do not regenerate after tuning."""
from pathlib import Path
import json,hashlib,datetime
ROOT=Path(__file__).resolve().parents[1]
ps=json.loads((ROOT/'corpora/sec/data/index.json').read_text())['passages']; byid={p['passage_id']:p for p in ps}
families=[
('employees','dev',['docu-k-68-0'],['How many employees did Docusign have?','What proportion of Docusign employees were based in the U.S.?']),
('integrations','heldout',['docu-k-1-0'],['How many active partner integrations does Docusign offer?','Did any single customer account for more than 10% of total revenue?']),
('competitor','dev',['docu-k-76-0'],['Who is the primary global competitor for eSignature?','Which electronic signature solution does Adobe offer?']),
('international','heldout',['docu-k-24-0','docu-q-16-0'],['Compare the disclosed international revenue growth rates between the filings.','Compare international revenue as a percentage of total revenue.']),
('hosting','dev',['docu-q-35-0'],['Why did hosting costs increase?','How much did information technology costs increase?']),
('credit','heldout',['docu-q-50-0'],['When does the credit facility mature?','What is the aggregate principal amount of the revolving credit facility?']),
('arr','dev',['docu-q-73-0'],['How does Docusign calculate annual recurring revenue?','What share of total ARR did IAM represent?']),
('customers','heldout',['docu-q-13-0'],['How many total customers did Docusign have as of July 31, 2026?','How many direct customers were served by the direct sales force?']),
('founding','dev',['ib1b89345a4364fb69d7ce3189f67b705_16'],['When was Albany founded?','Which industries are served by Albany engineered fabrics and composite components?']),
('products','heldout',['ain-k-5-0'],['What are the principal paper machine clothing products?','What share of Machine Clothing segment net revenues came from PMC products?']),
('raw_materials','dev',['ain-k-24-0'],['What are the primary raw materials for MC products?','What share of worldwide monofilament requirements does the Homer facility supply?']),
('operating_cash','heldout',['ain-k-291-0','ain-q-79-0'],['Compare the disclosed reasons for the decrease in cash provided by operating activities.','Compare the disclosed cash provided by operating activities amounts.']),
('liquidity','dev',['ain-k-296-0','ain-q-83-0'],['Compare total liquidity disclosed in the two filings.','Compare cash and cash equivalents disclosed in the two filings.']),
('interest','heldout',['ain-q-56-0'],['Why did net interest expense increase?','What contributed to higher interest expense, net?']),
('research','dev',['ain-q-50-0'],['Why did consolidated technical and research expenses decrease?','How much did consolidated technical and research expenses decrease?']),
('risk_updates','heldout',['i14dbd90247bd4fc9b423fff1380bd4ce_127'],['Were there material changes to previously disclosed risk factors?','What does the quarterly risk factors section say about changes?']),
('revenue','dev',['docu-q-31-0'],['Why did revenue increase?','How much did revenue increase in the three months ended July 31, 2026?']),
('fx','heldout',['docu-q-47-0'],['Why did foreign currency exchange losses increase?','Which currencies strengthened compared with the U.S. dollar?']),
('sales_channels','dev',['docu-k-49-0'],['What sales channels does Docusign use?','How does Docusign reach large commercial and enterprise companies?']),
('aec_materials','heldout',['ain-k-25-0'],['What are the primary raw materials in the AEC segment?','Why might alternative raw material suppliers be unavailable to AEC?']),
]
rows=[]
for fam,split,pids,questions in families:
 gold=[byid[x] for x in pids];docs=list(dict.fromkeys(p['accession'] for p in gold));sections={p['section'] for p in gold}
 for q in questions:
  rows.append(dict(id='r%02d'%(len(rows)+1),family=fam,split=split,question=q,scope=dict(company=gold[0]['ticker'],accessions=docs,section=next(iter(sections)) if len(sections)==1 else None),compare=len(docs)==2,answerable=True,gold=[dict(passage_id=p['passage_id'],accession=p['accession'],quote=p['text']) for p in gold],annotation='Source-authored by agent before retrieval development; not independently human verified.'))
neg=[
('dev','docu-k','What was employee compensation paid in Bitcoin?', 'Absent denomination'),
('dev','docu-k','How much revenue did customers on Mars generate?', 'Invented geography'),
('dev','docu-q','Why did an earthquake cause the reported revenue increase?', 'Unsupported causal premise'),
('dev','docu-q','On what exact day in May will the credit facility mature?', 'Only month and year disclosed'),
('dev','docu-q','Was cash provided by operating activities exactly $999 million?', 'False amount'),
('dev','ain-k','What is Docusign total liquidity?', 'Wrong company'),
('dev','ain-q','Predict next quarter operating cash flow.', 'Prediction'),
('dev','ain-q','What was total liquidity as of 2035-06-30?', 'Wrong date'),
('dev','ain-q','How much did the disclosed cybersecurity breach cost in dollars?', 'Risk is not realized loss'),
('dev','ain-k','What did the 10-K/A amendment say about raw materials?', 'Amendment absent'),
('heldout','docu-k','What was the exact number of employees based in the U.S.?', 'Only approximate percentage; unsupported exact calculation'),
('heldout','docu-k','How many active partner integrations are used on Venus?', 'Invented geography'),
('heldout','docu-q','What was the exact day in May when the credit facility agreement was signed?', 'Only month and year disclosed'),
('heldout','docu-q','Did IAM represent exactly 99% of total ARR?', 'False percentage'),
('heldout','docu-q','Why did a ransomware attack increase hosting costs?', 'Unsupported causal premise'),
('heldout','ain-k','Should I buy Albany stock based on its operating cash flow?', 'Investment advice'),
('heldout','ain-q','How much cash was lost because a port strike actually occurred?', 'Hypothetical risk is not event'),
('heldout','ain-q','What is cash and cash equivalents as of 2034-06-30?', 'Wrong date'),
('heldout','ain-q','What is Microsoft total liquidity?', 'Unknown entity'),
('heldout','ain-q','What is total liquidity in the 10-K/A?', 'Wrong form'),
]
for split,doc,q,why in neg:
 p=next(p for p in ps if p['id']==doc)
 rows.append(dict(id='r%02d'%(len(rows)+1),family='unsupported-'+str(len(rows)+1),split=split,question=q,scope=dict(company=p['ticker'],accessions=[p['accession']]),compare=False,answerable=False,gold=[],annotation=why))
assert len(rows)==60
out=ROOT/'evaluation/real'
for split in ['dev','heldout']:
 subset=[r for r in rows if r['split']==split];assert len(subset)==30 and sum(r['answerable'] for r in subset)==20
 (out/(split+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in subset))
files=['evaluation/real/dev.jsonl','evaluation/real/heldout.jsonl','corpora/sec/data/manifest.json','corpora/sec/data/index.json']
(out/'frozen.json').write_text(json.dumps(dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),label_origin='agent authored directly from source before retrieval development',human_independent=False,files={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in files}),indent=2)+'\n')
audit_ids=['docu-k-68-0','docu-k-1-0','docu-k-76-0','docu-k-24-0','docu-k-49-0','docu-q-35-0','docu-q-50-0','docu-q-73-0','docu-q-13-0','docu-q-47-0','ib1b89345a4364fb69d7ce3189f67b705_16','ain-k-5-0','ain-k-24-0','ain-k-291-0','ain-k-296-0','ain-q-56-0','ain-q-79-0','ain-q-83-0','ain-q-50-0','i14dbd90247bd4fc9b423fff1380bd4ce_127']
(out/'audit-selected.json').write_text(json.dumps([byid[x] for x in audit_ids],indent=2)+'\n')
print('Frozen 60 source-authored questions: 20 answerable + 10 unsupported per split.')
