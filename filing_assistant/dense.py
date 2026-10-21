"""Pretrained sentence-embedding retrieval (local model, no paid API).

Passage vectors are built once and pinned to the index digest, like the LSA
model. Queries are encoded at ask time, so the embedding package is needed
only for this method; BM25 and LSA stay standard-library only.
"""
import hashlib
import json
import math
import os
from array import array
from pathlib import Path

MODEL = 'BAAI/bge-small-en-v1.5'
# bge v1.5 retrieval convention: instruct the query, not the passages.
QUERY_PREFIX = 'Represent this sentence for searching relevant passages: '


def index_digest(index):
    return hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest()


class FastEmbedEncoder:
    """ONNX bge-small via fastembed; imported lazily so tests and BM25 users skip it."""
    def __init__(self, model=MODEL, cache_dir=None):
        from fastembed import TextEmbedding
        self.model = model
        self.engine = TextEmbedding(model_name=model, cache_dir=cache_dir or os.environ.get('FASTEMBED_CACHE_PATH'))

    def encode(self, texts):
        return [[float(v) for v in vector] for vector in self.engine.embed(list(texts), batch_size=64)]


def normalize(vector):
    norm = math.sqrt(sum(v*v for v in vector))
    return [v/norm for v in vector] if norm else list(vector)


def build_dense(index, directory, encoder=None):
    """Write dense.json (metadata) and dense.f32 (row-major little-endian float32)."""
    encoder = encoder or FastEmbedEncoder()
    vectors = [normalize(v) for v in encoder.encode(p['text'] for p in index['passages'])]
    dims = len(vectors[0])
    flat = array('f', (v for row in vectors for v in row))
    if flat.itemsize != 4:
        raise ValueError('float32 array required')
    directory = Path(directory)
    (directory/'dense.f32').write_bytes(flat.tobytes())
    meta = dict(schema_version=1, kind='pretrained sentence embedding', model=getattr(encoder, 'model', MODEL), dimensions=dims,
                query_prefix=QUERY_PREFIX, training_data='pretrained; no corpus fitting, evaluation questions or labels',
                index_digest=index_digest(index), vectors_sha256=hashlib.sha256((directory/'dense.f32').read_bytes()).hexdigest(),
                passage_ids=[p['passage_id'] for p in index['passages']])
    (directory/'dense.json').write_text(json.dumps(meta, indent=1) + '\n')
    return dict(passages=len(vectors), dimensions=dims, model=meta['model'])


class DenseRetriever:
    def __init__(self, index, directory, encoder=None):
        directory = Path(directory)
        self.meta = json.loads((directory/'dense.json').read_text())
        raw = (directory/'dense.f32').read_bytes()
        if self.meta['index_digest'] != index_digest(index):
            raise ValueError('Dense vectors do not match this index; rebuild them')
        if hashlib.sha256(raw).hexdigest() != self.meta['vectors_sha256']:
            raise ValueError('Dense vector file hash mismatch')
        flat = array('f'); flat.frombytes(raw)
        d = self.meta['dimensions']
        self.vectors = {pid: flat[i*d:(i+1)*d] for i, pid in enumerate(self.meta['passage_ids'])}
        self._encoder = encoder

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = FastEmbedEncoder(self.meta['model'])
        return self._encoder

    def embed_query(self, question):
        return normalize(self.encoder.encode([self.meta['query_prefix'] + question])[0])

    def rank(self, candidates, question):
        query = self.embed_query(question)
        hits = [dict(passage=p, score=sum(a*b for a, b in zip(query, self.vectors[p['passage_id']]))) for p in candidates]
        return sorted(hits, key=lambda h: (-h['score'], h['passage']['passage_id']))


def fuse(*rankings, k=60):
    """Reciprocal-rank fusion, same constant as the existing LSA hybrid."""
    fused = {}
    for ranking in rankings:
        for rank, hit in enumerate(ranking):
            pid = hit['passage']['passage_id']
            fused.setdefault(pid, dict(passage=hit['passage'], score=0.0))['score'] += 1/(k + rank + 1)
    return sorted(fused.values(), key=lambda h: (-h['score'], h['passage']['passage_id']))
