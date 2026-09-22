"""BM25, corpus-fitted LSA, and reciprocal-rank fusion; no online service."""
import gzip
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from .engine import Engine, tokens

class Retriever:
    def __init__(self, index, model_path=None):
        self.lexical = Engine(index)
        self.model = None
        if model_path:
            with gzip.open(model_path, 'rt') as f:
                self.model = json.load(f)
            digest = hashlib.sha256(json.dumps(index, sort_keys=True).encode()).hexdigest()
            if self.model['index_digest'] != digest:
                raise ValueError('Semantic model does not match this index; rebuild it')

    def rank(self, candidates, terms, method):
        bm = self.lexical.rank(candidates, terms)
        if method == 'bm25':
            return bm
        if method not in {'semantic', 'hybrid'} or self.model is None:
            raise ValueError('Select bm25, semantic or hybrid with a matching semantic model')
        m = self.model
        query = [0.0] * m['dimensions']
        for term in terms:
            vector = m['terms'].get(term)
            if vector:
                for i, value in enumerate(vector):
                    query[i] += value
        norm = math.sqrt(sum(v*v for v in query))
        if norm:
            query = [v/norm for v in query]
        semantic=[]
        for p in candidates:
            score = sum(a*b for a,b in zip(query,m['documents'][p['passage_id']]))
            matched = terms.intersection(self.lexical.term_counts[p['passage_id']])
            if score > 0:
                semantic.append(dict(passage=p,score=score,coverage=len(matched)/max(1,len(terms)),matched_terms=sorted(matched)))
        semantic.sort(key=lambda h:(-h['score'],h['passage']['passage_id']))
        if method == 'semantic':
            return semantic
        fused={}
        for ranking in (bm,semantic):
            for rank,h in enumerate(ranking):
                pid=h['passage']['passage_id']
                if pid not in fused:
                    fused[pid]=dict(h,score=0.0)
                fused[pid]['score']+=1/(60+rank+1)
        return sorted(fused.values(),key=lambda h:(-h['score'],h['passage']['passage_id']))


def build_semantic(index, destination, dimensions=64):
    """Build-time NumPy only. Fixed-seed randomized SVD over source TF-IDF."""
    import numpy as np
    counts=[Counter(tokens(p['text'])) for p in index['passages']]
    df=Counter(t for c in counts for t in c)
    vocab=sorted((t for t in df if df[t]>=2),key=lambda t:(-df[t],t))[:6000]
    ids={t:i for i,t in enumerate(vocab)}
    idf=np.array([math.log((1+len(counts))/(1+df[t]))+1 for t in vocab])
    matrix=np.zeros((len(counts),len(vocab)),dtype=np.float64)
    for row,c in enumerate(counts):
        for t,n in c.items():
            if t in ids: matrix[row,ids[t]]=(1+math.log(n))*idf[ids[t]]
    norms=np.linalg.norm(matrix,axis=1,keepdims=True)
    matrix/=np.maximum(norms,1e-12)
    k=min(dimensions,min(matrix.shape)-1)
    rng=np.random.default_rng(20260921)
    sample=matrix@rng.standard_normal((len(vocab),k+12))
    for _ in range(2):
        sample=matrix@(matrix.T@sample)
        sample=np.linalg.qr(sample,mode='reduced')[0]
    basis=np.linalg.qr(sample,mode='reduced')[0]
    _,_,vt=np.linalg.svd(basis.T@matrix,full_matrices=False)
    projection=vt[:k].T
    vectors=matrix@projection
    vectors/=np.maximum(np.linalg.norm(vectors,axis=1,keepdims=True),1e-12)
    payload=dict(schema_version=1,kind='corpus-fitted latent semantic analysis',dimensions=k,seed=20260921,training_data='source passages only; no evaluation questions or labels',index_digest=hashlib.sha256(json.dumps(index,sort_keys=True).encode()).hexdigest(),terms={t:np.round(projection[i]*idf[i],7).tolist() for i,t in enumerate(vocab)},documents={p['passage_id']:np.round(vectors[i],7).tolist() for i,p in enumerate(index['passages'])})
    with gzip.open(destination,'wt') as f:json.dump(payload,f,separators=(',',':'))
    return dict(documents=len(counts),terms=len(vocab),dimensions=k)
