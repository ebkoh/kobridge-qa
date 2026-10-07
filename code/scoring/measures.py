import re

from .matcher import chunk_hit, doc_from_text, table_tokens

DEPTH = 5


def _j(*xs):
    return " ".join(str(x) for x in xs if x)


def nows(s):
    return re.sub(r"\s+", "", s or "")


def quoted_passages(source_quote):
    out = []
    for p in re.findall(r'"([^"]+)"', source_quote or ""):
        p = p.replace("…", "...").split("...")[0]
        p = nows(p)
        if len(p) >= 8:
            out.append(p)
    return out


def view_source(u, heading):
    return {"doc": doc_from_text(u.get("source_document")), "heading": heading or "",
            "tabletext": _j(u.get("caption"), u.get("title"), u.get("table_id"))}


def view_body(u):
    return {"doc": doc_from_text(u.get("source_document")), "heading": u.get("text") or "",
            "tabletext": _j(u.get("caption"), u.get("title"), u.get("text"))}


def view_combined(u, heading):
    return {"doc": doc_from_text(u.get("source_document")),
            "heading": heading or u.get("text") or "",
            "tabletext": _j(u.get("caption"), u.get("title"), u.get("table_id"), u.get("text"))}


def mention_hit(u, qps, tabs):
    body = nows(u.get("text"))
    if any(p in body for p in qps):
        return True
    if tabs and (tabs & table_tokens(_j(u.get("caption"), u.get("title"),
                                        u.get("table_id"), u.get("text")))):
        return True
    return False


def take(units, depth=DEPTH, budget=None):
    if budget is None:
        return list(units[:depth])
    out, acc = [], 0
    for u in units:
        out.append(u)
        acc += len(u.get("text") or "")
        if acc >= budget:
            break
    return out


def score_units(g, qps, units, headings):
    s = c = m = j = False
    for u, h in zip(units, headings):
        s1 = chunk_hit(g, view_source(u, h), True)
        m1 = mention_hit(u, qps, g["tabs"])
        c = c or chunk_hit(g, view_body(u), True)
        s = s or s1
        m = m or m1
        j = j or (s1 and m1)
    return {"content": c, "source_label": s, "reference_mention": m, "joint_reference": j}


def source_label_hit(g, units, headings, table_ids):
    for u, h, tid in zip(units, headings, table_ids):
        uu = dict(u)
        uu["table_id"] = tid
        if chunk_hit(g, view_source(uu, h), True):
            return True
    return False


def evidence_units(g):
    return [("sec", x) for x in sorted(g["secnums"])] + [("tab", x) for x in sorted(g["tabs"])]


def full_evidence_coverage(g, units, headings):
    need = evidence_units(g)
    got = 0
    for kind, val in need:
        gu = dict(g)
        gu["secnums"] = {val} if kind == "sec" else set()
        gu["tabs"] = {val} if kind == "tab" else set()
        gu["title_text"] = ""
        if any(chunk_hit(gu, view_combined(u, h), True) for u, h in zip(units, headings)):
            got += 1
    return (bool(need) and got == len(need)), len(need), got
