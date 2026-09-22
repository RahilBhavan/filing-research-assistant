"""Optional public SEC fetch. Not used by the bundled fixture demo."""
import hashlib
import json
import os
import re
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def select_filings(submissions, as_of):
    date.fromisoformat(as_of)
    recent = submissions['filings']['recent']
    fields = ('form','filingDate','reportDate','accessionNumber','primaryDocument')
    if len({len(recent[k]) for k in fields}) != 1:
        raise ValueError('SEC submission columns have inconsistent lengths')
    rows = [dict(zip(fields,values)) for values in zip(*(recent[k] for k in fields))]
    rows = [r for r in rows if r['filingDate'] <= as_of]
    annuals = [r for r in rows if r['form']=='10-K']
    if not annuals:
        raise ValueError('No annual filing in recent metadata by cutoff; historical pagination is not implemented')
    annual = max(annuals,key=lambda r:(r['filingDate'],r['accessionNumber']))
    quarters = [r for r in rows if r['form']=='10-Q' and r['reportDate']>annual['reportDate'] and r['filingDate']>annual['filingDate']]
    if not quarters:
        raise ValueError('No subsequent 10-Q available by cutoff')
    return [annual,max(quarters,key=lambda r:(r['filingDate'],r['accessionNumber']))]


class SecClient:
    def __init__(self, user_agent):
        if not user_agent or '@' not in user_agent or '\n' in user_agent or '\r' in user_agent:
            raise ValueError('Set SEC_USER_AGENT to an application name and real contact email')
        self.user_agent = user_agent
        self.last_request = None

    def get(self, url):
        if not (url.startswith('https://data.sec.gov/submissions/') or url.startswith('https://www.sec.gov/Archives/edgar/data/')):
            raise ValueError('Only approved public SEC endpoints are supported')
        if self.last_request is not None:
            time.sleep(max(0,1.1-(time.monotonic()-self.last_request)))
        self.last_request = time.monotonic()
        request = Request(url,headers={'User-Agent':self.user_agent,'Accept-Encoding':'identity'})
        # Stop on access errors. Do not rotate identities or evade rate controls.
        try:
            with urlopen(request,timeout=30) as response:
                raw = response.read(25*1024*1024+1)
                if len(raw)>25*1024*1024:
                    raise ValueError('SEC response exceeds the 25 MB project limit')
                return raw
        except HTTPError as error:
            raise ValueError('SEC returned HTTP {}. Stop and review SEC access guidance.'.format(error.code)) from None


def fetch_corpus(destination, ciks, as_of, user_agent=None):
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError('Destination exists; choose a new folder to preserve the fixture corpus')
    if len(ciks)!=2 or len(set(ciks))!=2 or any(not re.fullmatch(r'\d{1,10}', c) for c in ciks):
        raise ValueError('Supply exactly two different numeric CIKs')
    if len({str(int(c)) for c in ciks}) != 2:
        raise ValueError('CIKs must identify two distinct companies')
    client = SecClient(user_agent or os.environ.get('SEC_USER_AGENT',''))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.sec-download-',dir=destination.parent) as temp:
        root = Path(temp)
        (root/'data/raw').mkdir(parents=True)
        (root/'data/metadata').mkdir()
        docs=[]
        for cik in ciks:
            cik=cik.zfill(10)
            url='https://data.sec.gov/submissions/CIK'+cik+'.json'
            raw_metadata=client.get(url)
            submissions=json.loads(raw_metadata)
            if str(submissions['cik']).zfill(10)!=cik:
                raise ValueError('SEC metadata CIK mismatch')
            (root/'data/metadata'/('CIK'+cik+'.json')).write_bytes(raw_metadata)
            for row in select_filings(submissions,as_of):
                accession=row['accessionNumber']
                primary=row['primaryDocument']
                if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',primary):
                    raise ValueError('Unexpected SEC document identifier')
                source='https://www.sec.gov/Archives/edgar/data/{}/{}/{}'.format(int(cik),accession.replace('-',''),primary)
                content=client.get(source)
                if b'<html' not in content[:5000].lower() or b'undeclared automated tool' in content.lower():
                    raise ValueError('SEC response is not a usable filing HTML document')
                local='data/raw/'+accession+'.html'
                (root/local).write_bytes(content)
                docs.append({'id':accession,'company':submissions['name'],'ticker':(submissions.get('tickers') or [cik])[0],'cik':cik,'accession':accession,'form':row['form'],'report_period':row['reportDate'],'filing_date':row['filingDate'],'source_kind':'sec','source_url':source,'local_path':local,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(content).hexdigest(),'is_amendment':False})
        manifest={'schema_version':1,'source_kind':'sec','corpus_date':as_of,'notice':'Public SEC filing corpus. Check original filings and parser coverage before relying on extracts.','documents':docs}
        (root/'data/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        # Parse before publishing the complete directory, so failures are recoverable.
        from .corpus import write_index
        write_index(root)
        root.rename(destination)
    return docs
