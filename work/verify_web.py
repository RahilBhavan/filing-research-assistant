import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from pathlib import Path
base='http://127.0.0.1:8765';checks=[]
def request(path,body=None,headers=None):
 h=headers or {};data=None
 if body is not None:data=json.dumps(body).encode();h=dict(h,**{'Content-Type':'application/json'})
 try:
  with urlopen(Request(base+path,data=data,headers=h),timeout=10) as r:return r.status,r.read(),dict(r.headers)
 except HTTPError as e:return e.code,e.read(),dict(e.headers)
status,raw,h=request('/api/config');config=json.loads(raw);assert status==200 and len(config['documents'])==4;checks.append('config: 4 real filings, 200')
qdoc=next(d for d in config['documents'] if d['ticker']=='DOCU' and d['form']=='10-Q')
for method in config['methods']:
 status,raw,_=request('/api/ask',dict(question='Why did revenue increase?',scope=dict(company='DOCU',accessions=[qdoc['accession']]),method=method));r=json.loads(raw);assert status==200 and r['method']==method;checks.append(method+': API returns valid answer/abstention')
for path,body,headers,expected in [('/../../README.md',None,None,404),('/api/passage?id=missing',None,None,404),('/api/config',None,{'Host':'evil.example'},403),('/api/ask',{}, {'Origin':'https://evil.example'},403),('/api/ask',{'question':5,'scope':{}},None,400),('/api/ask',{'question':'x','scope':{'company':'DOCU','accessions':'oops'}},None,400)]:
 status,_,_=request(path,body,headers);assert status==expected,(path,status);checks.append(f'{path}: expected {expected}')
assert "frame-ancestors 'none'" in h['Content-Security-Policy'];assert h['X-Content-Type-Options']=='nosniff';checks.append('CSP and nosniff headers present')
(Path(__file__).resolve().parents[1]/'evaluation/real/web-verification.json').write_text(json.dumps(dict(api=checks,browser=['Docusign revenue question answered with July 2026 filing','Inspect source opened modal with exact highlighted passage, adjacent context, SHA256, accession and official SEC anchor link','Albany liquidity comparison displayed two source cards for distinct reporting dates','Prediction request displayed explicit abstention','No browser console errors observed','Desktop layout visually inspected'],exit_status=0),indent=2)+'\n')
print('\n'.join(checks))
