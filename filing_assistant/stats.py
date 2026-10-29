"""Paired comparison statistics for the small frozen evaluation sets (standard library only).

Two systems answer the same questions, so per-question scores are paired. The
bootstrap resamples questions, not scores, and uses a fixed seed: the same
inputs always give the same interval.
"""
import math
import random

SEED = 20261029
RESAMPLES = 10000
CONFIDENCE = 0.95


def mean(values):
    return sum(values)/len(values)


def paired_bootstrap_ci(a, b, seed=SEED, resamples=RESAMPLES, confidence=CONFIDENCE):
    """Percentile interval for mean(a) - mean(b) over paired per-question scores."""
    if len(a) != len(b) or not a:
        raise ValueError('Paired scores must be non-empty and the same length')
    diffs = [x - y for x, y in zip(a, b)]
    n = len(diffs)
    rng = random.Random(seed)
    draws = []
    for _ in range(resamples):
        # random() rather than randrange/choices: its stream is stable across Python versions.
        total = sum(diffs[int(rng.random()*n)] for _ in range(n))
        draws.append(round(total/n, 12))  # rounding keeps float noise from straddling an exact zero
    draws.sort()
    tail = (1 - confidence)/2
    return draws[int(math.floor(tail*resamples))], draws[int(math.ceil((1 - tail)*resamples)) - 1]


def mcnemar_exact(a_only, b_only):
    """Two-sided exact McNemar p-value from the discordant counts (binomial test at p = 0.5)."""
    n = a_only + b_only
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(a_only, b_only) + 1))
    return min(1.0, 2*tail/2**n)


def compare(a, b, seed=SEED, resamples=RESAMPLES, confidence=CONFIDENCE):
    """Paired summary of a against b; adds the exact McNemar test when every score is 0 or 1."""
    lo, hi = paired_bootstrap_ci(a, b, seed, resamples, confidence)
    out = dict(n=len(a), mean_a=mean(a), mean_b=mean(b), diff=mean(a) - mean(b), ci_low=lo, ci_high=hi,
               confidence=confidence, resamples=resamples, seed=seed, interval_includes_zero=lo <= 0 <= hi)
    if all(v in (0, 1) for v in list(a) + list(b)):
        a_only = sum(x == 1 and y == 0 for x, y in zip(a, b))
        b_only = sum(x == 0 and y == 1 for x, y in zip(a, b))
        out.update(a_only=a_only, b_only=b_only, mcnemar_p=mcnemar_exact(a_only, b_only))
    return out
