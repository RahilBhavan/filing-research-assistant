import argparse
import json
import sys
from pathlib import Path
from .corpus import build_index, write_index
from .engine import Engine, Scope
from .evaluate import evaluate
from .sec import fetch_corpus

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
if not (DEFAULT_ROOT/'data/manifest.json').exists():
    # Installed package: data lives in the checkout, not site-packages.
    DEFAULT_ROOT = Path.cwd()


def main(argv=None):
    parser=argparse.ArgumentParser(description='Local filing research. Serve opens the real SEC corpus; legacy CLI defaults to fixtures.')
    parser.add_argument('--corpus',type=Path,default=DEFAULT_ROOT,help='Folder containing data/manifest.json')
    commands=parser.add_subparsers(dest='command',required=True)
    serve_parser=commands.add_parser('serve',help='Open the real SEC corpus in a localhost interface')
    serve_parser.add_argument('--port',type=int,default=8765)
    serve_parser.add_argument('--host',default='127.0.0.1',help='Bind address; use 0.0.0.0 only inside a container')
    commands.add_parser('ingest',help='Validate hashes and rebuild narrative index from local HTML')
    commands.add_parser('list',help='Show corpus provenance and exact scope values')
    ask=commands.add_parser('ask',help='Return cited narrative extracts or abstain')
    ask.add_argument('question')
    ask.add_argument('--company',required=True,help='Exact ticker, company name, or CIK')
    ask.add_argument('--accession',action='append',default=[])
    ask.add_argument('--form',choices=['10-K','10-Q','10-K/A','10-Q/A'])
    ask.add_argument('--period',help='Exact report period YYYY-MM-DD, not filing date')
    ask.add_argument('--section',choices=['business','mda','risks'])
    ask.add_argument('--compare',action='store_true',help='Require exactly two filings and evidence from each')
    ask.add_argument('--method',choices=['bm25','semantic','hybrid'],default='bm25')
    ask.add_argument('--json',action='store_true')
    cited=commands.add_parser('answer',help='Checked, cited LLM answer over one filing (treasury corpus)')
    cited.add_argument('question')
    cited.add_argument('--company',required=True,help='Exact ticker')
    cited.add_argument('--accession',action='append',default=[])
    cited.add_argument('--method',choices=['bm25','lsa','lsa-hybrid','dense','dense-hybrid'],default='dense-hybrid')
    cited.add_argument('--provider',choices=['anthropic','claude-cli','ollama','extractive'],help='Default: anthropic with ANTHROPIC_API_KEY, else extractive')
    cited.add_argument('--model')
    cited.add_argument('--json',action='store_true')
    commands.add_parser('evaluate',help='Run frozen bundled evaluation; --write rewrites reports').add_argument('--write',action='store_true',help='Rewrite evaluation/results.json and REPORT.md')
    fetch=commands.add_parser('fetch-sec',help='Optional network operation into a new corpus folder')
    fetch.add_argument('--cik',action='append',required=True)
    fetch.add_argument('--as-of',required=True)
    fetch.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args(argv)
    corpus=DEFAULT_ROOT/'corpora/sec' if args.command=='serve' and args.corpus==DEFAULT_ROOT else args.corpus
    if args.command!='fetch-sec' and not (corpus/'data/manifest.json').exists():
        print('Error: no corpus at {} (missing data/manifest.json); run from a checkout or pass --corpus'.format(corpus),file=sys.stderr)
        return 2
    try:
        if args.command=='serve':
            from .webapp import serve
            serve(corpus,args.port,args.host)
        elif args.command=='fetch-sec':
            docs=fetch_corpus(args.destination,args.cik,args.as_of)
            print('Downloaded {} SEC filings to {}'.format(len(docs),args.destination))
        elif args.command=='ingest':
            index=write_index(args.corpus)
            print(index['notice'])
            print(json.dumps({'passages':len(index['passages']),'documents':index['diagnostics']},indent=2))
        elif args.command=='list':
            index=build_index(args.corpus)
            print(index['notice'])
            seen=set()
            for p in index['passages']:
                if p['accession'] not in seen:
                    print('{} | {} | report {} | filed {} | {} | {}'.format(p['ticker'],p['form'],p['report_period'],p['filing_date'],p['accession'],p['source_kind']))
                    seen.add(p['accession'])
        elif args.command=='ask':
            index=build_index(args.corpus)
            if all(p['source_kind']=='sec' for p in index['passages']):
                from .research import ResearchEngine
                model=args.corpus/'data/semantic.json.gz'
                engine=ResearchEngine(index,model if model.exists() else None,args.method)
            else:
                engine=Engine(index)
            result=engine.ask(args.question,Scope(args.company,args.accession,args.form,args.period,args.section),args.compare)
            if args.json:
                print(json.dumps(result,indent=2))
            else:
                print(result['source_notice'])
                if result['status']=='abstained':
                    print("I can't establish that from the selected filings. Reason: " + result['reason'])
                else:
                    print('Selected narrative evidence' + (' by filing; no calculated change:' if args.compare else ':'))
                    for item in result['answer']:
                        c=item['citation']
                        target=c['source_url'] or (args.corpus/c['local_path']).resolve().as_uri()
                        if c['anchor']:
                            from urllib.parse import quote
                            target += '#' + quote(c['anchor'],safe='')
                        print('\n> '+item['excerpt'])
                        print('[{} | {} | report {} | filed {} | {} | {}]({})'.format(c['company'],c['form'],c['report_period'],c['filing_date'],c['section'],c['accession'],target))
                print('\n'+result['support_assessment'])
        elif args.command=='answer':
            from .cited import Retrieval, answer
            from .providers import make_provider
            result=answer(args.question,dict(company=args.company,accessions=args.accession),Retrieval(build_index(args.corpus),args.corpus),make_provider(args.provider,args.model),args.method)
            if args.json:
                print(json.dumps(result,indent=2))
            elif result['status']=='abstained':
                print('No checked answer ({}). Retrieved: {}'.format(result['reason'],', '.join(result['retrieved'])))
            else:
                print(result['answer'])
                for c in result['citations']:
                    print('\n> {}\n[{} | {} | report {} | {} | {}]({})'.format(c['quote'],c['company'],c['form'],c['report_period'],c['accession'],c['passage_id'],c['source_url']))
                print('\nProvider: {} · method: {}'.format(result['provider'],result['method']))
        elif args.command=='evaluate':
            report=evaluate(args.corpus,args.write)
            print(json.dumps({'dataset_size':report['dataset_size'],'metrics':report['metrics']},indent=2))
        return 0
    except (ValueError,OSError,KeyError,TypeError,RuntimeError) as error:
        print('Error: '+str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
