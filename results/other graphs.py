#!/usr/bin/env python3
"""Paired analysis of the thinking-disabled vs thinking-enabled eval runs.
Requires: numpy, scipy, matplotlib.

NOTE ON FORMATS
----------------
Turns out the final agent in the chain isn't consistently named the same
thing across files/cases -- some use "response_agent", others use
"actions_agent". Rather than hardcode one name, extraction resolves
whichever one is actually present as an author in each case's events.

Similarly, content.parts sometimes holds a single payload part (parts[0])
and sometimes holds a "thought" part (thought=true) followed by the actual
JSON payload part. _final_payload_text() handles both: it returns the first
part that isn't marked as a thought, falling back to the last part if every
part happens to be unmarked (which is exactly parts[0] for old-style
single-part content).

Both extract() (disabled) and extract_enabled() (enabled) share this same
robust logic; the only thing that differed between the two sample files
was cosmetic, so a single shared approach is used, called from both entry
points to keep the two runs auditable/labelled separately in main().
"""


import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats as sp

SCRIPT_DIR = Path(__file__).resolve().parent          # results/claude_generated
RESULTS = SCRIPT_DIR.parent / "results"                            # results/
FILES = {
    "disabled": RESULTS / "evalset_results/full_agent_full_agent_eval_set_large_12_disabled_1783532216.7194827.json",
    "enabled":  RESULTS / "evalset_results/full_agent_full_agent_eval_set_large_12_enabled_1783518451.6002152.json",
}
QUERY_TYPES_FILE = RESULTS / "ExcelQueries.json"
FIGDIR = SCRIPT_DIR / "thinking_mode_report_figs"

QT = ["Explicit one-step", "Implicit one-step", "Explicit multi-step",
      "Implicit multi-step", "Erroneous prompts"]
QT_SHORT = ["Explicit\none-step", "Implicit\none-step", "Explicit\nmulti-step",
            "Implicit\nmulti-step", "Erroneous\nprompts"]
OKABE_ITO = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7"]
BLUE, ORANGE = "#56B4E9", "#E69F00"   # disabled, enabled

# Canonical internal agent keys used everywhere downstream (rows["usage"][a],
# etc). These stay the same regardless of which file format we're reading.
AGENTS = ["root_agent", "triage_agent", "synthesis_agent", "response_agent"]

# Some files/cases name the final agent "response_agent", others
# "actions_agent". We try these, in order, per case.
FINAL_AGENT_CANDIDATES = ["response_agent", "actions_agent"]


# ---------------------------------------------------------------- extraction

def _final_payload_text(parts):
    """Return the non-thought text from a list of content parts.

    parts is sometimes a single payload part (old-style: parts[0] IS the
    payload) and sometimes a list where earlier parts carry
    {"thought": true} (the model's chain-of-thought) followed by the actual
    JSON payload part. We pick the first part NOT marked as a thought
    rather than assuming a fixed index, so this works for both layouts.
    """
    for p in parts:
        if not p.get("thought"):
            return p["text"]
    # fallback: every part was marked as a thought (shouldn't normally
    # happen) -- use the last part rather than crash
    return parts[-1]["text"]


def _resolve_final_agent(by):
    """Return whichever of FINAL_AGENT_CANDIDATES is present as an author
    in this case's events, or None if neither shows up (some cases appear
    to short-circuit straight from synthesis_agent to a templated final
    response with no dedicated agent invocation)."""
    for name in FINAL_AGENT_CANDIDATES:
        if name in by:
            return name
    return None


def _extract_common(path, qtype_map):
    """Shared extraction logic for both run types. Resolves the final
    agent's actual author name per case, and always parses the non-thought
    payload part, regardless of whether this particular file/case has
    thought parts or not."""
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)["evalCaseResults"]
    rows = []
    n_fallback = 0
    for c in cases:
        ev = c["sessionDetails"]["events"]
        # Some authors fire more than one event in a case (e.g. a later
        # state/tool event with no "content" field, such as the router
        # event). We want the content-bearing (JSON payload) event per
        # author for parsing, so only that kind of event is kept in `by`.
        by = {}
        for e in ev:
            if "content" in e and e["content"].get("parts"):
                by[e["author"]] = e
        # Timestamps are tracked separately across ALL events (content or
        # not), matching the original per-agent runtime semantics.
        ts = {e["author"]: e["timestamp"] for e in ev}
        final_agent = _resolve_final_agent(by)

        q = by["user"]["content"]["parts"][0]["text"]
        parsed = {}
        usage = {}
        for a in ["root_agent", "triage_agent", "synthesis_agent"]:
            ev_a = by[a]
            parsed[a] = json.loads(_final_payload_text(ev_a["content"]["parts"]))
            u = ev_a.get("usageMetadata") or {}
            usage[a] = {"prompt": u.get("promptTokenCount", 0),
                        "out": u.get("candidatesTokenCount", 0),
                        "thoughts": u.get("thoughtsTokenCount", 0)}

        if final_agent is not None:
            ev_f = by[final_agent]
            parsed["response_agent"] = json.loads(_final_payload_text(ev_f["content"]["parts"]))
            u = ev_f.get("usageMetadata") or {}
            usage["response_agent"] = {"prompt": u.get("promptTokenCount", 0),
                                       "out": u.get("candidatesTokenCount", 0),
                                       "thoughts": u.get("thoughtsTokenCount", 0)}
            final_ts = ts[final_agent]
        else:
            # No dedicated response/actions agent event in this case --
            # the workflow appears to have short-circuited straight to a
            # templated final response (e.g. no candidate POIs found).
            # Fall back to the case-level finalResponse for the payload;
            # since there's no discrete LLM invocation for this stage,
            # treat its runtime/tokens as zero and its "timestamp" as the
            # last known stage (synthesis_agent) so duration/rt_synthesis
            # come out as ~0 rather than crashing or being undefined.
            final_resp = (c["evalMetricResultPerInvocation"][0]
                          ["actualInvocation"]["finalResponse"]["parts"])
            parsed["response_agent"] = json.loads(_final_payload_text(final_resp))
            usage["response_agent"] = {"prompt": 0, "out": 0, "thoughts": 0}
            final_ts = ts.get("synthesis_agent", ts.get("triage_agent",
                       ts.get("root_agent", ts["user"])))
            n_fallback += 1

        rows.append({
            "query": q,
            "query_type": qtype_map[q],
            "pass": c["finalEvalStatus"] == 1,
            "score": c["overallEvalMetricResults"][0]["score"],
            # user message -> start of final response generation
            "duration": final_ts - ts["user"],
            # per-agent runtime = gap from own event to the next event
            "rt_root": ts["full_workflow"] - ts["root_agent"],
            "rt_triage": ts["synthesis_agent"] - ts["triage_agent"],
            "rt_synthesis": final_ts - ts["synthesis_agent"],
            "intent": parsed["root_agent"].get("intent"),
            "n_targets": len(parsed["triage_agent"].get("targets", [])),
            "pois_per_target": [len(v.get("selected_pois", []))
                                for v in parsed["synthesis_agent"].get("validations", [])],
            "cmds": [a.get("cmd") for a in parsed["response_agent"].get("actions", [])],
            "usage": usage,
        })
    if n_fallback:
        print(f"[{Path(path).name}] {n_fallback}/{len(cases)} cases had no "
              f"dedicated final-agent event; used case-level finalResponse "
              f"as a fallback (runtime/tokens for that stage set to 0).")
    return rows


def extract(path, qtype_map):
    """Extraction entry point for the thinking-disabled file."""
    return _extract_common(path, qtype_map)


def extract_enabled(path, qtype_map):
    """Extraction entry point for the thinking-enabled file."""
    return _extract_common(path, qtype_map)


def med_iqr(xs):
    return f"{np.median(xs):.2f} [{np.percentile(xs, 25):.2f}-{np.percentile(xs, 75):.2f}]"


def main():
    FIGDIR.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False})

    with open(QUERY_TYPES_FILE, encoding="utf-8") as f:
        qtype_map = {q: t for q, t in json.load(f)}
    D = {r["query"]: r for r in extract(FILES["disabled"], qtype_map)}
    E = {r["query"]: r for r in extract_enabled(FILES["enabled"], qtype_map)}
    assert sorted(D) == sorted(E), "query sets differ between runs"
    queries = sorted(D)

    # ------------------------------------------------------------ 1. quality
    print("### 1. QUALITY: response_match_score")
    for mode, M in [("disabled", D), ("enabled", E)]:
        s = [M[q]["score"] for q in queries]
        print(f"{mode}: mean={np.mean(s):.3f} median={np.median(s):.3f} "
              f"pass={sum(M[q]['pass'] for q in queries)}/75")
    sd = [D[q]["score"] for q in queries]
    se = [E[q]["score"] for q in queries]
    print(f"paired Wilcoxon on scores: p={sp.wilcoxon(sd, se).pvalue:.3f}")
    b = sum(D[q]["pass"] and not E[q]["pass"] for q in queries)
    c = sum(not D[q]["pass"] and E[q]["pass"] for q in queries)
    print(f"pass/fail flips: dis-pass/en-fail={b}, dis-fail/en-pass={c}")
    for t in QT:
        qs = [q for q in queries if D[q]["query_type"] == t]
        print(f"  {t:<22} dis median={np.median([D[q]['score'] for q in qs]):.3f} "
              f"pass={sum(D[q]['pass'] for q in qs)}/15 | "
              f"en median={np.median([E[q]['score'] for q in qs]):.3f} "
              f"pass={sum(E[q]['pass'] for q in qs)}/15")

    # ------------------------------------------------------------- 2. timing
    print("\n### 2. TIMING (user msg -> start of final generation)")
    for k, label in [("duration", "full pipeline"), ("rt_root", "root"),
                     ("rt_triage", "triage"), ("rt_synthesis", "synthesis")]:
        xd = [D[q][k] for q in queries]
        xe = [E[q][k] for q in queries]
        print(f"{label:<14} dis {med_iqr(xd)} | en {med_iqr(xe)} | "
              f"Wilcoxon p={sp.wilcoxon(xd, xe).pvalue:.3f}")
    for t in QT:
        qs = [q for q in queries if D[q]["query_type"] == t]
        print(f"  {t:<22} median dis {np.median([D[q]['duration'] for q in qs]):5.2f}"
              f" | en {np.median([E[q]['duration'] for q in qs]):5.2f}")

    # ------------------------------------------------------------- 3. tokens
    print("\n### 3. TOKENS per agent (median dis|en)")
    for a in AGENTS:
        parts = []
        for key in ["thoughts", "out", "prompt"]:
            xd = [D[q]["usage"][a][key] for q in queries]
            xe = [E[q]["usage"][a][key] for q in queries]
            p = (sp.wilcoxon(xd, xe).pvalue
                 if any(x != y for x, y in zip(xd, xe)) else 1.0)
            parts.append(f"{key}: {np.median(xd):.0f}|{np.median(xe):.0f} p={p:.3f}")
        print(f"  {a:<16} " + "  ".join(parts))
    for mode, M in [("disabled", D), ("enabled", E)]:
        tot = sum(M[q]["usage"][a][k] for q in queries for a in AGENTS
                  for k in ["out", "thoughts"])
        print(f"total generated tokens {mode}: {tot}")

    # ---------------------------------------------------------- 4. agreement
    print("\n### 4. BEHAVIOR AGREEMENT")
    print(f"same intent: {sum(D[q]['intent'] == E[q]['intent'] for q in queries)}/75 | "
          f"same n_targets: {sum(D[q]['n_targets'] == E[q]['n_targets'] for q in queries)}/75 | "
          f"same cmd sequence: {sum(D[q]['cmds'] == E[q]['cmds'] for q in queries)}/75")
    for mode, M in [("disabled", D), ("enabled", E)]:
        print(f"cmds {mode}: {dict(Counter(c for q in queries for c in M[q]['cmds']))}")
    for q in queries:
        if sorted(D[q]["cmds"]) != sorted(E[q]["cmds"]):
            print(f"  mismatch [{D[q]['query_type'][:18]:<18}] dis={D[q]['cmds']} "
                  f"en={E[q]['cmds']}  {q[:60]}")

    # ------------------------------------------------- 5. response-stage fit
    print("\n### 5. RESPONSE-AGENT RUNTIME ESTIMATION")
    gen, rt = [], []
    for M in (D, E):
        for q in queries:
            r = M[q]
            for a, k in [("root_agent", "rt_root"), ("triage_agent", "rt_triage"),
                         ("synthesis_agent", "rt_synthesis")]:
                gen.append(r["usage"][a]["thoughts"] + r["usage"][a]["out"])
                rt.append(r[k])
    gen, rt = np.array(gen), np.array(rt)
    slope, intercept = np.polyfit(gen, rt, 1)
    pred = intercept + slope * gen
    r2 = 1 - ((rt - pred) ** 2).sum() / ((rt - rt.mean()) ** 2).sum()
    print(f"fit: runtime = {intercept:.3f} s + {slope*1000:.2f} ms/token, "
          f"R2={r2:.3f}, resid SD={np.std(rt-pred):.2f}s, "
          f"rate={1/slope:.0f} tok/s, n={len(gen)}")

    def est(r):
        u = r["usage"]["response_agent"]
        return intercept + slope * (u["thoughts"] + u["out"])

    ed = np.array([est(D[q]) for q in queries])
    ee = np.array([est(E[q]) for q in queries])
    tot_d = np.array([D[q]["duration"] + est(D[q]) for q in queries])
    tot_e = np.array([E[q]["duration"] + est(E[q]) for q in queries])
    print(f"est response runtime: dis {med_iqr(ed)} | en {med_iqr(ee)} | "
          f"p={sp.wilcoxon(ed, ee).pvalue:.3f}")
    print(f"est end-to-end: dis median {np.median(tot_d):.2f}s | "
          f"en median {np.median(tot_e):.2f}s | "
          f"p={sp.wilcoxon(tot_d, tot_e).pvalue:.3f}")
    for t in QT:
        qs = [q for q in queries if D[q]["query_type"] == t]
        print(f"  {t:<22} est end-to-end median dis "
              f"{np.median([D[q]['duration']+est(D[q]) for q in qs]):5.2f} | en "
              f"{np.median([E[q]['duration']+est(E[q]) for q in qs]):5.2f}")

    # -------------------------------------------------------------- figures
    def grouped_box(ax, data_d, data_e, labels, width=0.28, offset=0.32,
                    xmargin=None):
        pos = np.arange(len(labels))
        for i, (data, col) in enumerate([(data_d, BLUE), (data_e, ORANGE)]):
            bp = ax.boxplot(data, positions=pos + (i - 0.5) * offset,
                            widths=width,
                            patch_artist=True, medianprops={"color": "black"},
                            flierprops={"markersize": 3})
            for box in bp["boxes"]:
                box.set_facecolor(col)
        ax.set_xticks(pos, labels)
        if xmargin is not None:
            ax.margins(x=xmargin)

    def mode_legend(ax):
        ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=BLUE),
                           plt.Rectangle((0, 0), 1, 1, fc=ORANGE)],
                  labels=["Thinking disabled", "Thinking enabled"], fontsize=9)

    # fig 1: paired scores
    fig, ax = plt.subplots(figsize=(5.5, 5.2))
    for t, col in zip(QT, OKABE_ITO):
        qs = [q for q in queries if D[q]["query_type"] == t]
        ax.scatter([D[q]["score"] for q in qs], [E[q]["score"] for q in qs],
                   s=38, color=col, label=t, alpha=0.85,
                   edgecolors="white", linewidths=0.5)
    ax.plot([0.3, 1.0], [0.3, 1.0], color="grey", lw=0.8, ls="--", zorder=0)
    ax.axhline(0.7, color="grey", lw=0.8, ls=":", zorder=0)
    ax.axvline(0.7, color="grey", lw=0.8, ls=":", zorder=0)
    ax.set_xlabel("response_match_score, thinking disabled")
    ax.set_ylabel("response_match_score, thinking enabled")
    ax.set_title("Paired per-query scores (dotted lines: 0.7 pass threshold)")
    ax.legend(fontsize=8, loc="lower left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig1_paired_scores.png", dpi=200)
    fig.savefig(FIGDIR / "fig1_paired_scores.pdf")
    plt.close(fig)

    # fig 2: latency by query type (portrait, Arial)
    with plt.rc_context({"font.family": "Arial", "pdf.fonttype": 42}):
        fig, ax = plt.subplots(figsize=(4.6, 6.0))
        grouped_box(ax,
                    [[D[q]["duration"] for q in queries if D[q]["query_type"] == t] for t in QT],
                    [[E[q]["duration"] for q in queries if E[q]["query_type"] == t] for t in QT],
                    QT_SHORT, width=0.38, offset=0.42, xmargin=0.02)
        ax.tick_params(axis="x", labelsize=8.5)
        ax.set_ylabel("Time to final generation start (s)")
        ax.set_title("Pipeline latency by query type\nand thinking mode")
        mode_legend(ax)
        fig.tight_layout()
        fig.savefig(FIGDIR / "fig2_latency_by_type.png", dpi=200)
        fig.savefig(FIGDIR / "fig2_latency_by_type.pdf")
        plt.close(fig)

    # fig 3: tokens per agent
    fig, axes = plt.subplots(1, 2, figsize=(9, 4), sharey=True)
    for ax, key, title in [(axes[0], "thoughts", "Thinking tokens"),
                           (axes[1], "out", "Output tokens")]:
        grouped_box(ax,
                    [[D[q]["usage"][a][key] for q in queries] for a in AGENTS],
                    [[E[q]["usage"][a][key] for q in queries] for a in AGENTS],
                    [a.replace("_agent", "") for a in AGENTS])
        ax.set_title(title)
    axes[0].set_ylabel("Tokens per invocation")
    mode_legend(axes[0])
    fig.suptitle("Per-agent token generation by thinking mode", y=0.98)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig3_tokens.png", dpi=200)
    fig.savefig(FIGDIR / "fig3_tokens.pdf")
    plt.close(fig)

    # fig 4: per-agent runtime
    fig, ax = plt.subplots(figsize=(6.5, 4))
    stages = [("rt_root", "Root"), ("rt_triage", "Triage"), ("rt_synthesis", "Synthesis")]
    grouped_box(ax,
                [[D[q][k] for q in queries] for k, _ in stages],
                [[E[q][k] for q in queries] for k, _ in stages],
                [n for _, n in stages])
    ax.set_ylabel("Runtime (s)")
    ax.set_title("Per-agent runtime by thinking mode\n"
                 "(response agent excluded: no end timestamp in logs)")
    mode_legend(ax)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig4_agent_runtime.png", dpi=200)
    fig.savefig(FIGDIR / "fig4_agent_runtime.pdf")
    plt.close(fig)

    # fig 5: token-runtime model
    fig, ax = plt.subplots(figsize=(6.8, 4.6))
    per_agent = {"root_agent": [], "triage_agent": [], "synthesis_agent": []}
    for M in (D, E):
        for q in queries:
            r = M[q]
            for a, k in [("root_agent", "rt_root"), ("triage_agent", "rt_triage"),
                         ("synthesis_agent", "rt_synthesis")]:
                per_agent[a].append((r["usage"][a]["thoughts"] + r["usage"][a]["out"], r[k]))
    for (a, pts), col in zip(per_agent.items(), OKABE_ITO):
        ax.scatter([g for g, _ in pts], [t for _, t in pts], s=14, color=col,
                   alpha=0.6, label=a.replace("_agent", ""), edgecolors="none")
    xs = np.linspace(0, gen.max() * 1.05, 100)
    ax.plot(xs, intercept + slope * xs, color="black", lw=1.2,
            label=f"fit: {intercept:.2f} s + {slope*1000:.1f} ms/token (R²={r2:.2f})")
    respg = np.array([M[q]["usage"]["response_agent"]["thoughts"]
                      + M[q]["usage"]["response_agent"]["out"]
                      for M in (D, E) for q in queries])
    ax.scatter(respg, intercept + slope * respg, marker="x", s=18,
               color="#D55E00", alpha=0.7, label="response agent (predicted)")
    ax.set_xlabel("Generated tokens (thinking + output)")
    ax.set_ylabel("Measured runtime (s)")
    ax.set_title("Runtime vs generated tokens, 450 measured LLM invocations")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig5_token_runtime_model.png", dpi=200)
    fig.savefig(FIGDIR / "fig5_token_runtime_model.pdf")
    plt.close(fig)

    # fig 6: estimated response runtime + end-to-end by type
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), width_ratios=[1, 2])
    ax = axes[0]
    bp = ax.boxplot([ed, ee], positions=[0, 1], widths=0.5, patch_artist=True,
                    medianprops={"color": "black"}, flierprops={"markersize": 3})
    for box, col in zip(bp["boxes"], [BLUE, ORANGE]):
        box.set_facecolor(col)
    ax.set_xticks([0, 1], ["Thinking\ndisabled", "Thinking\nenabled"])
    ax.set_ylabel("Estimated runtime (s)")
    ax.set_title("Estimated response-agent\nruntime")
    ax = axes[1]
    grouped_box(ax,
                [[D[q]["duration"] + est(D[q]) for q in queries if D[q]["query_type"] == t] for t in QT],
                [[E[q]["duration"] + est(E[q]) for q in queries if E[q]["query_type"] == t] for t in QT],
                QT_SHORT)
    ax.set_ylabel("Estimated end-to-end latency (s)")
    ax.set_title("Estimated end-to-end latency by query type\n"
                 "(measured pipeline + estimated response stage)")
    mode_legend(ax)
    fig.tight_layout()
    fig.savefig(FIGDIR / "fig6_estimated_end_to_end.png", dpi=200)
    fig.savefig(FIGDIR / "fig6_estimated_end_to_end.pdf")
    plt.close(fig)

    print(f"\nfigures written to {FIGDIR}")


if __name__ == "__main__":
    main()