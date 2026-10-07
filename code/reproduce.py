import argparse, csv, json, os, statistics as st, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from stats import paired_bootstrap, mcnemar_exact, holm, wilson   # noqa: E402

DEPTH = 5
IDX = ["C1", "C2", "C3", "C4"]
MEAS = ["content", "source_label", "reference_mention", "joint_reference"]
TYPES = ["T1", "T2", "T3", "T4"]
SIM_FLOOR = 0.3          # floor applied to s = 1 - 2(1 - cos)^2 at retrieval time
GPT = "gpt-4o-2024-08-06"
FAMILY_12 = ["closed_book", "one_passage", "bm25_original", "three_passages", "ten_passages",
             "rerank_pool10", "rerank_pool20", "rerank_pool30", "bm25_repaired",
             "heading_path_overlap", "C1", "C3"]


def lj(name):
    with open(os.path.join(REPO, "results", name), encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def f6(x):
    return "%.6f" % x


def g6(x):
    return "%.6g" % x


def write(out, name, header, rows):
    with open(os.path.join(out, name), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow(r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "reproduced"))
    out = ap.parse_args().out
    os.makedirs(out, exist_ok=True)

    # inputs 
    RET = defaultdict(dict)                     # (index, condition) -> id -> row
    for r in lj("retrieval_per_item.jsonl"):
        RET[(r["index"], r["condition"])][r["id"]] = r
    D5 = {c: RET[(c, "depth5")] for c in IDX}
    SV = {c: RET[(c, "similar_volume")] for c in ("C2", "C4")}
    LAB = sorted(D5["C1"])                       # labeled items (retrieval denominator)
    TYPE = {q: D5["C1"][q]["type"] for q in LAB}

    ANSW = defaultdict(dict)                    # (model, configuration) -> id -> row
    for r in lj("answers_per_item.jsonl"):
        ANSW[(r["model"], r["configuration"])][r["id"]] = r
    G = {cfg: ANSW[(GPT, cfg)] for (m, cfg) in ANSW if m == GPT}
    ALL = sorted(G["C4"])
    ITYPE = {q: G["C4"][q]["type"] for q in ALL}
    KEY = {q: G["C4"][q]["keyed_idx"] for q in ALL}
    OK = {cfg: {q: G[cfg][q]["correct"] for q in ALL} for cfg in G}

    TOK = defaultdict(dict)
    for r in lj("tokens_per_item.jsonl"):
        TOK[r["index"]][r["id"]] = r["prompt_tokens"]

    FF = defaultdict(dict)
    for r in lj("freeform_pilot.jsonl"):
        FF[r["configuration"]][r["id"]] = r
    UNITS = lj("index_units.jsonl")

    def hits(F, m, ids):
        return {q: F[q][m] for q in ids}

    # index outcomes 
    rows = []
    for c in IDX:
        for m in MEAS:
            for subset, ids in (("all labeled", LAB), ("T3", [q for q in LAB if TYPE[q] == "T3"])):
                k = sum(1 for q in ids if D5[c][q][m])
                rows.append([c, m, subset, k, len(ids), f6(100 * k / len(ids))])
    write(out, "index_outcomes_depth5.csv",
          ["index", "measure", "items", "hits", "n", "recall_pct"], rows)

    rows = []
    for c in IDX:
        k, n = sum(OK[c].values()), len(ALL)
        lo, hi = wilson(k, n)
        tv = [TOK[c][q] for q in ALL]
        rows.append([c, k, n, f6(100 * k / n), f6(100 * lo), f6(100 * hi),
                     f6(st.mean(tv)), len(tv),
                     "yes" if any(u["table_id"] for u in UNITS if u["index"] == c) else "no"])
    write(out, "index_accuracy_tokens.csv",
          ["index", "correct", "n", "accuracy_pct", "wilson_low_pct", "wilson_high_pct",
           "mean_prompt_tokens", "token_items", "stores_table_identifiers"], rows)

    # paired contrasts
    C = []

    def contrast(family, a, b, measure, subset, first, second, ids):
        d, (lo, hi) = paired_bootstrap(second, first, ids)
        gn, ls, p = mcnemar_exact(second, first, ids)
        C.append({"family": family, "contrast": "%s to %s" % (a, b), "measure": measure,
                  "items": subset, "n": len(ids), "first_hits": sum(first[q] for q in ids),
                  "second_hits": sum(second[q] for q in ids), "difference_pp": d,
                  "ci_low_pp": lo, "ci_high_pp": hi, "gained": gn, "lost": ls, "p_exact": p})

    D5_ROWS = [(a, b, m) for a, b in (("C1", "C2"), ("C1", "C3"), ("C3", "C4"), ("C2", "C4"))
               for m in MEAS]
    for a, b, m in D5_ROWS:
        contrast("depth5", a, b, m, "all labeled", hits(D5[a], m, LAB), hits(D5[b], m, LAB), LAB)
    for t in TYPES:
        ids = [q for q in LAB if TYPE[q] == t]
        contrast("by_type", "C3", "C4", "content", t, hits(D5["C3"], "content", ids),
                 hits(D5["C4"], "content", ids), ids)
    for m in MEAS:
        contrast("similar_volume", "C2", "C4", m, "all labeled", hits(SV["C2"], m, LAB),
                 hits(SV["C4"], m, LAB), LAB)
    for a, b in (("C1", "C2"), ("C2", "C4"), ("C3", "C4")):
        contrast("accuracy", a, b, "accuracy", "all items", OK[a], OK[b], ALL)
    # Holm families: the 19 depth-five index contrasts (16 retrieval + 3 accuracy), and the four per-type tests
    fam = {"depth5": "depth5+accuracy", "accuracy": "depth5+accuracy", "by_type": "by_type"}
    for name in ("depth5+accuracy", "by_type"):
        sel = [i for i, r in enumerate(C) if fam.get(r["family"]) == name]
        adj = holm({i: C[i]["p_exact"] for i in sel})
        for i in sel:
            C[i]["holm_family"], C[i]["p_holm"] = name, adj[i]
    write(out, "paired_contrasts.csv",
          ["family", "contrast", "measure", "items", "n", "first_hits", "second_hits",
           "difference_pp", "ci_low_pp", "ci_high_pp", "gained", "lost", "p_exact",
           "holm_family", "p_holm"],
          [[r["family"], r["contrast"], r["measure"], r["items"], r["n"], r["first_hits"],
            r["second_hits"], f6(r["difference_pp"]), f6(r["ci_low_pp"]), f6(r["ci_high_pp"]),
            r["gained"], r["lost"], g6(r["p_exact"]), r.get("holm_family", ""),
            g6(r["p_holm"]) if "p_holm" in r else ""] for r in C])

    # decomposition of the C1-to-C2 source-label difference
    STEP = {s: {q: D5["C1"][q]["decomposition"][s] for q in LAB} for s in "ABC"}
    STEP["D"] = {q: D5["C2"][q]["decomposition"]["D"] for q in LAB}
    CONT = {"A": "C1", "B": "C1", "C": "C1", "D": "C2"}
    rows, prev = [], None
    for s in "ABCD":
        k = sum(STEP[s].values())
        kc = sum(1 for q in LAB if D5[CONT[s]][q]["content"])
        r = [s, CONT[s], k, len(LAB), f6(100 * k / len(LAB))]
        if prev:
            d, (lo, hi) = paired_bootstrap(STEP[s], STEP[prev], LAB)
            gn, ls, p = mcnemar_exact(STEP[s], STEP[prev], LAB)
            r += [f6(d), f6(lo), f6(hi), gn, ls, g6(p)]
        else:
            r += ["", "", "", "", "", ""]
        r += [kc, f6(100 * kc / len(LAB))]
        rows.append(r)
        prev = s
    write(out, "decomposition.csv",
          ["step", "retrieval", "source_label_hits", "n", "source_label_pct",
           "difference_from_previous_pp", "ci_low_pp", "ci_high_pp", "gained", "lost",
           "p_exact", "content_hits", "content_pct"], rows)

    rows = []
    for rule in ("max_overlap", "start_offset"):
        h1 = {q: D5["C1"][q]["attribution"][rule] for q in LAB}
        h2 = {q: D5["C2"][q]["attribution"][rule] for q in LAB}
        d, (lo, hi) = paired_bootstrap(h2, h1, LAB)
        rows.append([rule, sum(h1.values()), sum(h2.values()), len(LAB), f6(d), f6(lo), f6(hi)])
    write(out, "attribution_rules.csv",
          ["heading_rule_for_both_indexes", "C1_hits", "C2_hits", "n", "difference_pp",
           "ci_low_pp", "ci_high_pp"], rows)

    # similar volume
    budget = int(st.median([D5["C4"][q]["chars"] for q in LAB]))
    within = sum(1 for q in LAB if SV["C2"][q]["chars"]
                 and abs(SV["C4"][q]["chars"] - SV["C2"][q]["chars"]) <= 0.10 * SV["C2"][q]["chars"])
    rows = [["budget_chars", "median over labeled items of the C4 top-five character total",
             budget]]
    for c in ("C2", "C4"):
        rows.append(["%s_mean_chars" % c, "mean realized characters at the budget",
                     f6(st.mean(SV[c][q]["chars"] for q in LAB))])
        rows.append(["%s_mean_units" % c, "mean realized units at the budget",
                     f6(st.mean(SV[c][q]["n_units"] for q in LAB))])
    rows.append(["items_within_10pct", "|C4 - C2| <= 0.10 x C2 characters at the budget", within])
    rows.append(["n", "labeled items", len(LAB)])
    write(out, "similar_volume.csv", ["quantity", "definition", "value"], rows)

    # configuration accuracy (GPT-4o, 14 configurations)
    raw, fav = {}, {}
    for cfg in FAMILY_12:
        gn, ls, p = mcnemar_exact(OK[cfg], OK["C4"], ALL)   # gained = cfg right, C4 wrong
        raw[cfg], fav[cfg] = p, (ls, gn)
    adj = holm(raw)
    rows = []
    for cfg in ["C4"] + FAMILY_12 + ["C2"]:
        k = sum(OK[cfg].values())
        lo, hi = wilson(k, len(ALL))
        up = sum(1 for q in ALL if not G[cfg][q]["parsed"])
        if cfg in raw:
            extra = [fav[cfg][0], fav[cfg][1], g6(raw[cfg]), g6(adj[cfg])]
        else:
            extra = ["", "", "", ""]
        rows.append([cfg, k, len(ALL), f6(100 * k / len(ALL)), f6(100 * lo), f6(100 * hi)]
                    + extra + [up])
    write(out, "pipeline_accuracy.csv",
          ["configuration", "correct", "n", "accuracy_pct", "wilson_low_pct", "wilson_high_pct",
           "favoring_C4", "favoring_configuration", "p_exact_vs_C4", "p_holm_12", "unparsed"],
          rows)

    rows = []
    for (m, cfg), R in sorted(ANSW.items()):
        if m == GPT:
            continue
        k = sum(1 for q in R if R[q]["correct"])
        rows.append([m, cfg, k, len(R), f6(100 * k / len(R)),
                     sum(1 for q in R if not R[q]["parsed"])])
    write(out, "local_generators.csv",
          ["model", "configuration", "correct", "n", "accuracy_pct", "unparsed"], rows)

    # multi-hop full-evidence coverage 
    T4 = [q for q in LAB if TYPE[q] == "T4"]
    rows = []
    for c in IDX:
        allm = {q: D5[c][q]["multihop"]["all_matched"] for q in T4}
        ok = [q for q in T4 if OK[c][q]]
        rows.append([c, len(T4), sum(allm.values()), f6(100 * sum(allm.values()) / len(T4)),
                     len(ok), sum(1 for q in ok if not allm[q])])
    write(out, "multihop_coverage.csv",
          ["index", "multihop_items", "all_labeled_units_matched", "pct", "correct",
           "correct_with_unit_unmatched"], rows)

    # free-form pilot
    SUB = sorted(FF["C4"])
    rows = []
    for cfg in ("closed_book", "C1", "C2", "C4"):
        R = FF[cfg]
        k = sum(1 for q in SUB if R[q]["correct"])
        mc = sum(1 for q in SUB if OK[cfg][q])
        rows.append([cfg, len(SUB), k, f6(100 * k / len(SUB)), mc, f6(100 * mc / len(SUB)),
                     sum(1 for q in SUB if R[q]["provision_cited"]),
                     sum(1 for q in SUB if not R[q]["parsed"])])
    write(out, "freeform_pilot.csv",
          ["configuration", "n", "freeform_correct", "freeform_pct", "mc_correct_same_items",
           "mc_pct_same_items", "provision_cited", "unparsed"], rows)
    a = {q: FF["closed_book"][q]["correct"] for q in SUB}
    b = {q: FF["C4"][q]["correct"] for q in SUB}
    gn, ls, p = mcnemar_exact(b, a, SUB)
    write(out, "freeform_pilot_contrast.csv",
          ["contrast", "n", "favoring_C4", "favoring_closed_book", "p_exact"],
          [["closed_book to C4, free-form correct", len(SUB), gn, ls, g6(p)]])

    # benchmark and index facts
    rows = [["items", "all items", len(ALL)],
            ["labeled_items", "items in the retrieval denominator", len(LAB)],
            ["labeled_items_with_table", "labeled items whose label names a table",
             sum(1 for q in LAB if D5["C1"][q]["label_has_table"])],
            ["median_question_evidence_jaccard", "median over labeled items",
             "%.6f" % st.median(D5["C1"][q]["question_evidence_jaccard"] for q in LAB)],
            ["items_with_full_evidence_record", "T4 labeled items", len(T4)],
            ["items_T4_all", "T4 items among all items", sum(1 for q in ALL if ITYPE[q] == "T4")]]
    for t in TYPES + ["T5"]:
        rows.append(["items_%s" % t, "items of type %s" % t, sum(1 for q in ALL if ITYPE[q] == t)])
    for pos in range(4):
        rows.append(["keyed_position_%d" % (pos + 1), "keyed answer at option %d" % (pos + 1),
                     sum(1 for q in ALL if KEY[q] == pos)])
    for c in IDX:
        rows.append(["units_%s" % c, "units in index %s" % c,
                     sum(1 for u in UNITS if u["index"] == c)])
        rows.append(["units_%s_with_table_id" % c, "units of %s carrying a table identifier" % c,
                     sum(1 for u in UNITS if u["index"] == c and u["table_id"])])
    write(out, "benchmark_index_facts.csv", ["quantity", "definition", "value"], rows)

    # derived figures
    mt = {c: st.mean(TOK[c][q] for q in ALL) for c in IDX}
    acc = {c: 100 * sum(OK[c].values()) / len(ALL) for c in IDX}
    chg = sum(1 for q in LAB
              if [u[3:] for u in D5["C1"][q]["unit_ids"]] != [u[3:] for u in D5["C2"][q]["unit_ids"]])
    bt = {r["items"]: r for r in C if r["family"] == "by_type"}
    net = {t: bt[t]["lost"] - bt[t]["gained"] for t in TYPES}
    d34 = [r for r in C if r["family"] == "depth5" and r["contrast"] == "C3 to C4"
           and r["measure"] == "content"][0]
    up = {cfg: sum(1 for q in ALL if not G[cfg][q]["parsed"]) for cfg in G}
    pf = {k: sum(1 for cfg in G for q in ALL if G[cfg][q].get("parse_failure") == k)
          for k in ("refusal", "format")}
    pf_cfg = {k: sorted({cfg for cfg in G for q in ALL if G[cfg][q].get("parse_failure") == k})
              for k in ("refusal", "format")}
    sig = [r for r in C if r.get("holm_family") == "depth5+accuracy" and r["p_holm"] < 0.05]
    rows = [
        ["prompt_tokens_C4_vs_C3_fewer_pct", "100 x (1 - mean C4 / mean C3)",
         f6(100 * (1 - mt["C4"] / mt["C3"]))],
        ["prompt_tokens_C4_vs_C1_fewer_pct", "100 x (1 - mean C4 / mean C1)",
         f6(100 * (1 - mt["C4"] / mt["C1"]))],
        ["prompt_tokens_C1_minus_C2", "mean C1 - mean C2", f6(mt["C1"] - mt["C2"])],
        ["accuracy_min_C1_to_C4_pct", "lowest index accuracy", f6(min(acc.values()))],
        ["accuracy_max_C1_to_C4_pct", "highest index accuracy", f6(max(acc.values()))],
        ["source_label_gain_steps_A_to_C_pp", "decomposition step C minus step A",
         f6(100 * (sum(STEP["C"].values()) - sum(STEP["A"].values())) / len(LAB))],
        ["reembedding_changed_items", "labeled items whose C1 and C2 top-five windows differ",
         chg],
        ["c3_to_c4_content_net_lost", "lost minus gained, all labeled items",
         d34["lost"] - d34["gained"]],
        ["c3_to_c4_content_net_lost_T1_T2_T4", "lost minus gained in T1, T2 and T4",
         net["T1"] + net["T2"] + net["T4"]],
        ["holm_p_T1_of_four_type_tests", "Holm-adjusted p of the T1 test", g6(bt["T1"]["p_holm"])],
        ["holm_depth5_significant", "contrasts with Holm-adjusted p < 0.05",
         "; ".join("%s %s" % (r["contrast"], r["measure"]) for r in sig)],
        ["holm_depth5_significant_n", "count", len(sig)],
        ["holm_depth5_significant_max_p", "largest adjusted p among them",
         g6(max(r["p_holm"] for r in sig)) if sig else ""],
        ["unparsed_all_gpt4o", "unparsed responses, 14 GPT-4o configurations",
         sum(up.values())],
        ["unparsed_closed_book", "unparsed responses, closed book", up["closed_book"]],
        ["unparsed_other", "unparsed responses, other configurations",
         sum(v for k, v in up.items() if k != "closed_book")],
        ["unparsed_other_configurations", "configurations with an unparsed response",
         "; ".join(sorted(k for k, v in up.items() if v and k != "closed_book"))],
        ["unparsed_refusal", "unparsed responses that decline to answer", pf["refusal"]],
        ["unparsed_refusal_configurations", "configurations with a refusal",
         "; ".join(pf_cfg["refusal"])],
        ["unparsed_format", "unparsed responses in which no option can be identified",
         pf["format"]],
        ["unparsed_format_configurations", "configurations with a format failure",
         "; ".join(pf_cfg["format"])],
        ["similarity_floor_cosine", "cosine at which 1 - 2(1 - cos)^2 equals 0.3",
         f6(1 - ((1 - SIM_FLOOR) / 2) ** 0.5)],
    ]
    write(out, "derived_figures.csv", ["quantity", "definition", "value"], rows)
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
