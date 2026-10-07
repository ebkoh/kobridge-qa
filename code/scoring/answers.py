# Multiple-choice answer parsing and the free-form provision-citation rule
import re

from .matcher import SECNUM_RE, TABLE_TOK


def parse_answer(raw):
    m = re.search(r'[1,2,3,4]', raw)
    if m:
        return '1,2,3,4'.index(m.group())
    m = re.search(r'[\(\s]?([1-4])\)', raw)
    if m:
        return int(m.group(1)) - 1
    m = re.search(r'Answer\s*[:：]?\s*([1-4])', raw)
    if m:
        return int(m.group(1)) - 1
    stripped = raw.strip()
    if stripped and stripped[0] in '1234':
        return int(stripped[0]) - 1
    return -1


def gold_pointers(item):
    sp = item.get("section_path", {}) or {}
    parts = []
    for t in (sp.get("subsection"), sp.get("section"), sp.get("section_title")):
        if t:
            s = str(t)
            if "Evidence" in s:
                s = s.split("Evidence", 1)[1]
            parts.append(s)
    secnums = set()
    for s in parts:
        secnums |= set(SECNUM_RE.findall(s))
    tabs = set()
    for t in (item.get("table_refs") or []):
        tabs |= set(TABLE_TOK.findall(str(t).replace(" ", "")))
    for st in ((item.get("evidence", {}) or {}).get("supporting_tables") or []):
        tabs |= set(TABLE_TOK.findall(str(st.get("id", "")).replace(" ", "")))
    return secnums, tabs


def provision_match(item, provision):

    if not provision:
        return False
    secnums, tabs = gold_pointers(item)
    pv = str(provision)
    for sn in sorted(secnums):
        if re.search(r"(?<![\d.])" + re.escape(sn) + r"(?![\d])", pv) is not None:
            return True
    pv_ns = pv.replace(" ", "").replace("-", ".")
    for tb in sorted(tabs):
        if tb.replace("-", ".") in pv_ns:
            return True
    return False
