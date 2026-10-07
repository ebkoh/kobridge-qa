def holm(pvalues):

    order = sorted(pvalues, key=lambda k: pvalues[k])
    m = len(order)
    out, run = {}, 0.0
    for i, name in enumerate(order):
        run = max(run, min(1.0, (m - i) * pvalues[name]))
        out[name] = run
    return out
