"""Small repeatable localhost concurrency smoke test."""
import argparse
import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8765/api/ask')
    parser.add_argument('--requests', type=int, default=40)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    payload = json.dumps({
        'question': 'Why did revenue increase?',
        'scope': {'company': 'DOCU', 'accessions': ['0001261333-26-000099'], 'section': None},
        'compare': False, 'method': 'bm25',
    }).encode()

    def once(_):
        started = time.perf_counter()
        request = Request(args.url, data=payload, headers={'Content-Type': 'application/json'})
        with urlopen(request, timeout=15) as response:
            body = json.load(response)
            if response.status != 200 or body['status'] != 'answered':
                raise RuntimeError('Unexpected response')
        return (time.perf_counter() - started) * 1000

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        timings = list(pool.map(once, range(args.requests)))
    timings.sort()
    print(json.dumps({
        'requests': len(timings), 'workers': args.workers, 'errors': 0,
        'median_ms': round(statistics.median(timings), 1),
        'p95_ms': round(timings[max(0, int(len(timings) * .95) - 1)], 1),
        'max_ms': round(max(timings), 1),
    }, indent=2))


if __name__ == '__main__':
    main()

