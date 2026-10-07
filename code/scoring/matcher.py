import re

TABLE_TOK = re.compile(r"Table\d+[.\-]\d+")
SECNUM_RE = re.compile(r"\d+(?:\.\d+)+")


def doc_from_text(*texts):
    s = " ".join(str(t) for t in texts if t)
    s_ns = s.replace(" ", "")
    if ("Type3" in s_ns) or ("Type3" in s_ns) or ("02.+" in s) or s.startswith("02"):
        return "facility_type3_manual"
    if ("Bridge" in s_ns) or ("Manual" in s_ns) or ("01." in s) or ("01 " in s):
        return "bridge_guideline"
    return None


def norm(s):
    return (s or "").replace(" ", "")


def heading_has_section(heading, secnum):
    if not heading or not secnum:
        return False
    return re.search(r"(?<![\d.])" + re.escape(secnum) + r"(?![\d])", heading) is not None


def table_tokens(*texts):
    toks = set()
    for t in texts:
        if not t:
            continue
        toks |= set(TABLE_TOK.findall(str(t).replace(" ", "")))
    return toks


def extract_secnums(*texts):
    nums = set()
    for t in texts:
        if not t:
            continue
        s = str(t)
        if "Evidence" in s:
            s = s.split("Evidence", 1)[1]
        for m in SECNUM_RE.findall(s):
            nums.add(m)
    return nums


def gold_info(item):
    sp = item.get("section_path", {}) or {}
    sub = (sp.get("subsection") or "").strip()
    sec = (sp.get("section") or "").strip()
    title = (sp.get("section_title") or "").strip()
    is_t5 = item.get("type", "").startswith("T5")
    secnums = extract_secnums(sub, sec, title)
    title_text = title
    if "Evidence" in title_text:
        title_text = title_text.split("/")[0]
    title_text = title_text.replace("Up-title:", "").replace("Up-subtitle:", "").strip()
    tabs = set()
    for t in (item.get("table_refs") or []):
        tabs |= table_tokens(t)
    for st in ((item.get("evidence", {}) or {}).get("supporting_tables") or []):
        tabs |= table_tokens(st.get("id"))
    code = (item.get("document", {}) or {}).get("code")
    answerable = (not is_t5) and (bool(secnums) or bool(tabs))
    return dict(secnums=secnums, title_text=title_text, tabs=tabs, code=code,
                answerable=answerable, is_t5=is_t5)


def chunk_hit(g, view, has_source=True):
    """True when the view carries the label g.

    1. document: if both sides name a single manual, they must agree
    2. any labeled section number in view['heading'] (heading_has_section)
    3. or the title (4+ characters, half-width spaces removed) inside view['heading']
    4. or a labeled table number among the table numbers of view['tabletext']
    """
    cdoc = view.get("doc")
    if has_source and cdoc is not None and g["code"] not in ("both", None):
        if cdoc != g["code"]:
            return False
    for sn in sorted(g["secnums"]):
        if heading_has_section(view.get("heading"), sn):
            return True
    tt = g.get("title_text") or ""
    if len(tt) >= 4 and norm(tt) in norm(view.get("heading")):
        return True
    if g["tabs"] and (g["tabs"] & table_tokens(view.get("tabletext"))):
        return True
    return False
