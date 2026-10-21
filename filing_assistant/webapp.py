"""Local-only interface. Raw filing HTML is never served or executed."""
import json
import logging
import os
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from .cited import Retrieval, answer
from .corpus import build_index
from .engine import Scope
from .research import ResearchEngine

STATIC=Path(__file__).with_name('static')
LOG=logging.getLogger('filing_assistant.web')

def make_handler(corpus,allowed_hosts=(),provider=None,answers_per_minute=30):
    index=build_index(corpus)
    model=Path(corpus)/'data/semantic.json.gz'
    engines={m:ResearchEngine(index,model if model.exists() else None,m) for m in (['bm25','semantic','hybrid'] if model.exists() else ['bm25'])}
    retrieval=Retrieval(index,corpus)
    answer_method='dense-hybrid' if retrieval.dense else 'bm25'
    if provider is None:
        from .providers import make_provider
        provider=make_provider(os.environ.get('FILING_PROVIDER') or None)
    recent=deque();lock=threading.Lock()
    def admit():
        # A public deployment calls a paid API: cap answers per minute per process.
        with lock:
            now=time.monotonic()
            while recent and now-recent[0]>60:recent.popleft()
            if len(recent)>=answers_per_minute:return False
            recent.append(now);return True
    documents=list({p['accession']:{k:p[k] for k in ['company','ticker','accession','form','report_period','filing_date','source_url','sha256','source_kind']} for p in index['passages']}.values())
    passages={p['passage_id']:p for p in index['passages']}
    class Handler(BaseHTTPRequestHandler):
        def send(self,status,payload,mime='application/json; charset=utf-8'):
            body=json.dumps(payload).encode() if isinstance(payload,(dict,list)) else payload
            self.send_response(status)
            self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers();self.wfile.write(body)
        def allowed(self):
            port=self.server.server_port
            hosts={'127.0.0.1:'+str(port),'localhost:'+str(port)}|set(allowed_hosts)
            if self.headers.get('Host') not in hosts:
                self.send(403,{'error':'Local host required'});return False
            origin=self.headers.get('Origin')
            if origin and origin not in {scheme+host for host in hosts for scheme in ('http://','https://')}:
                self.send(403,{'error':'Same-origin requests required'});return False
            return True
        def do_GET(self):
            if not self.allowed():return
            path=urlsplit(self.path)
            static={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path.path in static:
                f=STATIC/static[path.path];mime={'html':'text/html','js':'text/javascript','css':'text/css'}[f.suffix[1:]]
                self.send(200,f.read_bytes(),mime+'; charset=utf-8')
            elif path.path=='/api/config':
                self.send(200,dict(documents=documents,methods=list(engines),default_method='bm25',notice=index['notice'],passages=len(passages),answer=dict(provider=provider.name,method=answer_method)))
            elif path.path=='/api/passage':
                pid=parse_qs(path.query).get('id',[''])[0];p=passages.get(pid)
                if not p:self.send(404,{'error':'Passage not found'});return
                same=[a for a in index['passages'] if a['accession']==p['accession'] and a['section']==p['section']]
                pos=next(i for i,a in enumerate(same) if a['passage_id']==pid)
                self.send(200,dict(selected=p,context=same[max(0,pos-1):pos+2]))
            else:self.send(404,{'error':'Not found'})
        def do_POST(self):
            if not self.allowed():return
            if self.path not in ('/api/ask','/api/answer'):self.send(404,{'error':'Not found'});return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=8192:raise ValueError('Request must be 1–8192 bytes')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('JSON required')
                body=json.loads(self.rfile.read(n))
                if not isinstance(body,dict):raise ValueError('JSON object required')
                q=body['question'];scope=body['scope'];compare=body.get('compare',False);method=body.get('method','bm25')
                if not isinstance(q,str) or not q.strip() or len(q)>1000:raise ValueError('Enter a question of 1–1000 characters')
                if not isinstance(scope,dict) or set(scope)-{'company','accessions','section'}:raise ValueError('Invalid scope')
                if not isinstance(scope.get('company'),str):raise ValueError('Select a company')
                acc=scope.get('accessions',[])
                if not isinstance(acc,list) or not all(isinstance(a,str) for a in acc) or len(acc)>2:raise ValueError('Select at most two filings')
                if scope.get('section') not in {None,'business','mda','risks'}:raise ValueError('Invalid section')
                if self.path=='/api/answer':
                    if compare or len(acc)>1 or scope.get('section'):raise ValueError('Cited answers use one filing and all sections')
                    if not admit():self.send(429,{'error':'Answer limit reached; try again in a minute'});return
                    try:
                        result=answer(q.strip(),dict(company=scope['company'],accessions=acc),retrieval,provider,answer_method)
                    except (RuntimeError,OSError) as e:
                        LOG.warning('Answer provider failed error_type=%s',type(e).__name__)
                        self.send(502,{'error':'Answer provider unavailable'});return
                    result.pop('raw',None)
                    self.send(200,result);return
                if type(compare) is not bool or method not in engines:raise ValueError('Invalid comparison or retrieval method')
                self.send(200,engines[method].ask(q.strip(),Scope(**scope),compare))
            except (ValueError,KeyError,TypeError) as e:
                LOG.warning('Rejected API request path=%s error_type=%s',self.path,type(e).__name__)
                # Only our own ValueError messages are shown; parser and key errors stay generic.
                self.send(400,{'error':str(e) if type(e) is ValueError else 'Invalid request'})
        def log_message(self,format,*args):
            # Do not log user questions or source payloads.
            return
    return Handler

class Server(ThreadingHTTPServer):
    request_queue_size=64

def serve(corpus,port=8765,host='127.0.0.1'):
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s')
    # Extra Host headers to accept, e.g. the Azure Container Apps FQDN. Empty by default.
    allowed=[h.strip() for h in os.environ.get('FILING_ALLOWED_HOSTS','').split(',') if h.strip()]
    server=Server((host,port),make_handler(corpus,allowed,answers_per_minute=int(os.environ.get('FILING_ANSWERS_PER_MINUTE','30'))))
    LOG.info('Server started host=%s port=%s corpus=%s',host,server.server_port,Path(corpus).resolve())
    print('Filing research: http://127.0.0.1:'+str(server.server_port),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
