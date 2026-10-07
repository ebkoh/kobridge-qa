import re

TOKEN_RE = re.compile(r"[가-힣]{2,}|[A-Za-z]{2,}|\d+(?:\.\d+)+")


def tokset(s):
    return set(TOKEN_RE.findall(s or ""))


def question_evidence_jaccard(item):
    """Token-set Jaccard between the question and the whole evidence.source_quote."""
    a = tokset(item.get("question"))
    b = tokset((item.get("evidence", {}) or {}).get("source_quote", ""))
    return len(a & b) / len(a | b) if (a | b) else 0.0
