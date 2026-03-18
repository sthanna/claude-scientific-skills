#!/usr/bin/env python3
"""
Generate a PRISMA 2020 flow diagram from a search log JSON.

Usage:
    python scripts/prisma_diagram.py \
      --log results/search_log.json \
      --screened-excluded 842 \
      --fulltext-assessed 124 \
      --fulltext-excluded 89 \
      --fulltext-reasons "wrong population:23,no outcome data:31,non-RCT:35" \
      --included 35 \
      --output figures/prisma_flow.png

Requires: uv pip install matplotlib
"""

import json
import argparse
from pathlib import Path


def draw_prisma(counts: dict, output: str):
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    fig, ax = plt.subplots(figsize=(10, 14))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis("off")

    def box(x, y, w, h, text, color="#1a3a52", textcolor="white", fontsize=9):
        rect = mpatches.FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.1", linewidth=1.5,
            edgecolor=color, facecolor=color if textcolor == "white" else "white"
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center", fontsize=fontsize,
                color=textcolor, wrap=True,
                multialignment="center", fontfamily="sans-serif")

    def arrow(x1, y1, x2, y2):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="->", color="#555555", lw=1.5))

    def side_box(x, y, w, h, text):
        rect = mpatches.FancyBboxPatch(
            (x - w/2, y - h/2), w, h,
            boxstyle="round,pad=0.1", linewidth=1,
            edgecolor="#cc4444", facecolor="#fff5f5"
        )
        ax.add_patch(rect)
        ax.text(x, y, text, ha="center", va="center", fontsize=8,
                color="#cc4444", multialignment="center")

    # Title
    ax.text(5, 13.5, "PRISMA 2020 Flow Diagram", ha="center", va="center",
            fontsize=13, fontweight="bold", color="#1a3a52")

    # Phase labels
    for label, y in [("Identification", 12.2), ("Screening", 9.5),
                     ("Eligibility", 6.5), ("Included", 3.5)]:
        ax.text(0.6, y, label, ha="center", va="center", fontsize=9,
                color="#1a3a52", fontweight="bold",
                bbox=dict(boxstyle="round", facecolor="#e8f4f8", edgecolor="#1a3a52", alpha=0.7))

    # --- Identification ---
    db_counts = counts.get("database_counts", {})
    db_lines = "\n".join(f"{db}: n={n}" for db, n in db_counts.items()) or f"n={counts.get('total_raw', '?')}"
    box(4, 12.2, 4.5, 1.2, f"Records identified from databases\n({db_lines})", fontsize=8)
    arrow(4, 11.6, 4, 10.8)

    # --- Screening ---
    total_raw = counts.get("total_raw", "?")
    after_dedup = counts.get("after_dedup", "?")
    dupes = counts.get("duplicates_removed", "?")

    box(4, 10.4, 4.5, 1.0, f"Records after deduplication\n(n={after_dedup})")
    side_box(8.2, 10.4, 2.8, 0.8, f"Duplicates removed\n(n={dupes})")
    ax.annotate("", xy=(6.7, 10.4), xytext=(6.2, 10.4),
                arrowprops=dict(arrowstyle="->", color="#cc4444", lw=1))

    arrow(4, 9.9, 4, 9.1)
    screened_excluded = counts.get("screened_excluded", "?")
    box(4, 8.7, 4.5, 1.0, f"Records screened\n(title/abstract, n={after_dedup})")
    side_box(8.2, 8.7, 2.8, 0.8, f"Excluded\n(n={screened_excluded})")
    ax.annotate("", xy=(6.7, 8.7), xytext=(6.2, 8.7),
                arrowprops=dict(arrowstyle="->", color="#cc4444", lw=1))

    # --- Eligibility ---
    arrow(4, 8.2, 4, 7.4)
    fulltext_assessed = counts.get("fulltext_assessed", "?")
    fulltext_excluded = counts.get("fulltext_excluded", "?")
    box(4, 7.0, 4.5, 1.0, f"Full texts assessed for eligibility\n(n={fulltext_assessed})")

    # Reasons for exclusion
    reasons = counts.get("fulltext_exclusion_reasons", {})
    if reasons:
        reason_text = "Excluded (n={}):\n".format(fulltext_excluded)
        reason_text += "\n".join(f"• {r}: {n}" for r, n in list(reasons.items())[:5])
    else:
        reason_text = f"Excluded\n(n={fulltext_excluded})"
    side_box(8.2, 7.0, 2.8, 1.2, reason_text)
    ax.annotate("", xy=(6.7, 7.0), xytext=(6.2, 7.0),
                arrowprops=dict(arrowstyle="->", color="#cc4444", lw=1))

    # --- Included ---
    arrow(4, 6.5, 4, 5.5)
    included = counts.get("included", "?")
    box(4, 5.0, 4.5, 1.2,
        f"Studies included in synthesis\n(n={included})",
        color="#00a8a8")

    plt.tight_layout()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor="white")
    print(f"PRISMA diagram saved to {output}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True, help="Path to search_log.json")
    parser.add_argument("--screened-excluded", type=int, default=None)
    parser.add_argument("--fulltext-assessed", type=int, default=None)
    parser.add_argument("--fulltext-excluded", type=int, default=None)
    parser.add_argument("--fulltext-reasons", default=None,
                        help="Comma-separated 'reason:count' pairs")
    parser.add_argument("--included", type=int, required=True)
    parser.add_argument("--output", default="figures/prisma_flow.png")
    args = parser.parse_args()

    with open(args.log) as f:
        search_log = json.load(f)

    counts = dict(search_log)
    counts["database_counts"] = search_log.get("counts", {})

    if args.screened_excluded is not None:
        counts["screened_excluded"] = args.screened_excluded
    if args.fulltext_assessed is not None:
        counts["fulltext_assessed"] = args.fulltext_assessed
    if args.fulltext_excluded is not None:
        counts["fulltext_excluded"] = args.fulltext_excluded
    if args.fulltext_reasons:
        reasons = {}
        for pair in args.fulltext_reasons.split(","):
            if ":" in pair:
                r, n = pair.rsplit(":", 1)
                reasons[r.strip()] = int(n.strip())
        counts["fulltext_exclusion_reasons"] = reasons
    counts["included"] = args.included

    draw_prisma(counts, args.output)


if __name__ == "__main__":
    main()
