import random

SEED, B_REPS = 42, 10000


def paired_bootstrap(second, first, ids, B=B_REPS, seed=SEED):
    rnd = random.Random(seed)
    n = len(ids)
    diffs = [(1.0 if second[i] else 0.0) - (1.0 if first[i] else 0.0) for i in ids]
    reps = []
    for _ in range(B):
        s = 0.0
        for _j in range(n):
            s += diffs[rnd.randrange(n)]
        reps.append(s / n)
    reps.sort()
    return (100 * sum(diffs) / n,
            (100 * reps[int(0.025 * B)], 100 * reps[int(0.975 * B) - 1]))
