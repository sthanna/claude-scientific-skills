#!/usr/bin/env python3
"""
Generate interactive co-authorship and keyword networks.

Usage:
    python scripts/network.py \
      --input results/papers.json \
      --mode coauthorship \
      --min-papers 3 \
      --output results/coauthor_network.html

    python scripts/network.py \
      --input results/papers.json \
      --mode keywords \
      --output results/keyword_map.html

Requires: uv pip install networkx pyvis pandas
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def build_coauthorship_network(papers: list, min_papers: int = 2) -> tuple:
    """Build author co-authorship network. Returns (nodes, edges)."""
    author_papers = defaultdict(int)
    author_names = {}
    author_insts = {}
    coauthorship = defaultdict(int)

    for p in papers:
        authors = p.get("authorships", [])
        author_ids = []
        for auth in authors:
            a = auth.get("author", {})
            aid = a.get("id", "")
            if not aid:
                continue
            author_papers[aid] += 1
            author_names[aid] = a.get("display_name", "Unknown")
            insts = auth.get("institutions", [])
            if insts:
                author_insts[aid] = insts[0].get("display_name", "")
            author_ids.append(aid)

        # Add edges for each co-authorship pair
        for i in range(len(author_ids)):
            for j in range(i + 1, len(author_ids)):
                a1, a2 = sorted([author_ids[i], author_ids[j]])
                coauthorship[(a1, a2)] += 1

    # Filter to authors with enough papers
    active = {aid for aid, n in author_papers.items() if n >= min_papers}

    nodes = [
        {"id": aid, "label": author_names.get(aid, "?"),
         "title": f"{author_names.get(aid,'?')}\n{author_insts.get(aid,'')}\n{author_papers[aid]} papers",
         "size": 8 + author_papers[aid] * 2,
         "institution": author_insts.get(aid, "Unknown")}
        for aid in active
    ]

    edges = [
        {"source": a1, "target": a2, "weight": w}
        for (a1, a2), w in coauthorship.items()
        if a1 in active and a2 in active
    ]

    return nodes, edges


def build_keyword_network(papers: list, min_count: int = 3) -> tuple:
    """Build keyword co-occurrence network."""
    keyword_count = defaultdict(int)
    cooccurrence = defaultdict(int)

    for p in papers:
        kws = [k.get("display_name", "").lower() for k in p.get("keywords", [])]
        concepts = [c.get("display_name", "").lower() for c in p.get("concepts", [])[:5]
                    if c.get("score", 0) > 0.4]
        all_terms = list(set(kws + concepts))

        for t in all_terms:
            if t:
                keyword_count[t] += 1
        for i in range(len(all_terms)):
            for j in range(i + 1, len(all_terms)):
                t1, t2 = sorted([all_terms[i], all_terms[j]])
                if t1 and t2:
                    cooccurrence[(t1, t2)] += 1

    active = {kw for kw, n in keyword_count.items() if n >= min_count and len(kw) > 2}

    nodes = [
        {"id": kw, "label": kw,
         "title": f"{kw}: {keyword_count[kw]} papers",
         "size": 6 + keyword_count[kw]}
        for kw in active
    ]

    edges = [
        {"source": t1, "target": t2, "weight": w}
        for (t1, t2), w in cooccurrence.items()
        if t1 in active and t2 in active and w >= 2
    ]

    return nodes, edges


def render_html_network(nodes: list, edges: list, output: str, title: str = "Network"):
    """Render interactive network using pyvis."""
    try:
        from pyvis.network import Network
    except ImportError:
        print("pyvis not installed. Run: uv pip install pyvis")
        # Fallback: save as JSON for manual inspection
        fallback = {"nodes": nodes, "edges": edges}
        out = output.replace(".html", "_data.json")
        with open(out, "w") as f:
            json.dump(fallback, f, indent=2)
        print(f"Saved network data to {out} (install pyvis for HTML output)")
        return

    net = Network(height="800px", width="100%", bgcolor="#0d1b2a",
                  font_color="white", notebook=False)
    net.set_options("""
    {
      "physics": {"stabilization": {"iterations": 200}},
      "nodes": {"borderWidth": 1, "shadow": true},
      "edges": {"smooth": {"type": "continuous"}, "shadow": true}
    }
    """)

    # Color by institution (coauthorship) or frequency bucket (keywords)
    import hashlib
    COLORS = ["#00a8a8", "#4fc3f7", "#81d4fa", "#b3e5fc", "#80cbc4",
              "#a5d6a7", "#fff59d", "#ffcc80", "#ef9a9a", "#ce93d8"]

    inst_colors = {}
    for node in nodes:
        inst = node.get("institution", "")
        if inst not in inst_colors:
            idx = len(inst_colors) % len(COLORS)
            inst_colors[inst] = COLORS[idx]
        color = inst_colors[inst]

        net.add_node(
            node["id"], label=node["label"],
            title=node.get("title", node["label"]),
            size=node.get("size", 10),
            color=color
        )

    for edge in edges:
        net.add_edge(edge["source"], edge["target"],
                     value=edge.get("weight", 1))

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(output)
    print(f"  Network saved: {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--mode", default="coauthorship",
                        choices=["coauthorship", "keywords"])
    parser.add_argument("--min-papers", type=int, default=2,
                        help="Min papers per author (coauthorship mode)")
    parser.add_argument("--min-keyword-count", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)
    papers = data if isinstance(data, list) else data.get("records", data)

    if args.mode == "coauthorship":
        print("Building co-authorship network...")
        nodes, edges = build_coauthorship_network(papers, args.min_papers)
        print(f"  {len(nodes)} authors, {len(edges)} collaborations")
        render_html_network(nodes, edges, args.output, "Co-authorship Network")
    else:
        print("Building keyword co-occurrence network...")
        nodes, edges = build_keyword_network(papers, args.min_keyword_count)
        print(f"  {len(nodes)} keywords, {len(edges)} co-occurrences")
        render_html_network(nodes, edges, args.output, "Keyword Map")


if __name__ == "__main__":
    main()
