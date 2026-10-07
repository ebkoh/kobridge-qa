import math

def mcnemar_exact(second, first, ids):

    gained = sum(1 for q in ids if second[q] and not first[q])
    lost = sum(1 for q in ids if first[q] and not second[q])
    n = gained + lost
    if n == 0:
        return gained, lost, 1.0
    k = min(gained, lost)
    return gained, lost, min(1.0, 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2.0 ** n))
