"""Pick the tasks for a session: spread by curriculum domain weights, optionally missed-first."""
import random

# CNCF CKA curriculum v1.37 domain weights (see exam/README.md for the quoted source)
DOMAIN_WEIGHTS = {
    "Storage": 10,
    "Workloads and Scheduling": 15,
    "Servicing and Networking": 20,
    "Troubleshooting": 30,
    "Cluster Architecture, Installation and Configuration": 25,
}
SESSION_SIZE = 16


def allocate(avail, n, weights=DOMAIN_WEIGHTS):
    """How many tasks to take from each domain: largest-remainder split of n by weight, each
    domain capped at avail[domain]; whatever a capped domain cannot give is re-split among the
    domains that still have tasks. Returns {domain: count}; sum is min(n, sum(avail))."""
    n = min(n, sum(avail.values()))
    got = {d: 0 for d in weights}
    left = n
    while left > 0:
        open_d = [d for d in weights if got[d] < avail.get(d, 0)]
        if not open_d:
            break
        total = sum(weights[d] for d in open_d)
        quota = {d: left * weights[d] / total for d in open_d}
        base = {d: min(int(quota[d]), avail[d] - got[d]) for d in open_d}
        give = sum(base.values())
        rem = sorted(open_d, key=lambda d: (quota[d] - int(quota[d]), weights[d]), reverse=True)
        for d in rem:
            if give >= left:
                break
            if base[d] < avail[d] - got[d]:
                base[d] += 1
                give += 1
        for d in open_d:
            got[d] += base[d]
        left -= give
        if give == 0:
            break
    return got


def weighted_pick(tasks, n, rng, weights=DOMAIN_WEIGHTS):
    by = {d: [t for t in tasks if t["domain"] == d] for d in weights}
    quota = allocate({d: len(v) for d, v in by.items()}, n, weights)
    chosen = []
    for d, k in quota.items():
        chosen += rng.sample(by[d], k)
    return chosen


def select_session(pool, counted_ids=(), mode="weighted", n=SESSION_SIZE, rng=None,
                   weights=DOMAIN_WEIGHTS):
    """mode 'weighted': spread by domain weights over the whole pool.
    mode 'missed': tasks that have never counted first (still spread by weight among them);
    only if fewer than n exist is the rest filled from tasks that have counted."""
    rng = rng or random.Random()
    counted_ids = set(counted_ids)
    if mode == "missed":
        missed = [t for t in pool if t["id"] not in counted_ids]
        chosen = weighted_pick(missed, min(n, len(missed)), rng, weights)
        if len(chosen) < n:
            done = [t for t in pool if t["id"] in counted_ids]
            chosen += weighted_pick(done, n - len(chosen), rng, weights)
    else:
        chosen = weighted_pick(pool, n, rng, weights)
    rng.shuffle(chosen)
    return chosen
