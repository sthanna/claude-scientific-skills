#!/usr/bin/env python3
"""
Visualize a knowledge graph as interactive HTML or static PNG.

Usage:
    # Interactive HTML (pyvis)
    python scripts/visualize.py \
      --graph results/knowledge_graph.json \
      --output results/kg_visualization.html

    # Static PNG focused on one entity
    python scripts/visualize.py \
      --graph results/knowledge_graph.json \
      --output results/kg_figure.png \
      --format png \
      --focus-entity "bedaquiline" \
      --hops 2

Requires: uv pip install networkx pyvis matplotlib
"""

import json
import argparse
from pathlib import Path

# Entity type colors (teal/navy palette matching scientific theme)
ENTITY_COLORS = {
    "Drug":          "#00a8a8",  # teal
    "Gene/Protein":  "#4fc3f7",  # light blue
    "Disease":       "#ef5350",  # red
    "Pathway":       "#66bb6a",  # green
    "Mechanism":     "#ffa726",  # orange
    "Organism":      "#ab47bc",  # purple
    "Assay":         "#78909c",  # grey
    "Cell Type":     "#26c6da",  # cyan
    "default":       "#90a4ae",  # grey-blue
}

RELATION_COLORS = {
    "INHIBITS":         "#ef5350",
    "ACTIVATES":        "#66bb6a",
    "BINDS":            "#00a8a8",
    "TREATS":           "#42a5f5",
    "CAUSES":           "#ff7043",
    "ASSOCIATED_WITH":  "#ab47bc",
    "PART_OF":          "#26c6da",
    "CO_MENTIONED":     "#78909c",
    "default":          "#90a4ae",
}


def load_graph(path: str):
    with open(path) as f:
        data = json.load(f)
    nodes = {n["id"]: n for n in data.get("nodes", [])}
    edges = data.get("edges", [])
    return nodes, edges


def get_subgraph(nodes: dict, edges: list, focus: str, hops: int = 2):
    """Extract subgraph around a focus entity up to N hops."""
    focus = focus.lower()
    if focus not in nodes:
        # Try partial match
        matches = [nid for nid in nodes if focus in nid]
        if not matches:
            print(f"Entity '{focus}' not found. Available: {list(nodes.keys())[:10]}")
            return nodes, edges
        focus = matches[0]
        print(f"Matched: {focus}")

    included = {focus}
    for _ in range(hops):
        new = set()
        for e in edges:
            if e["source"] in included:
                new.add(e["target"])
            if e["target"] in included:
                new.add(e["source"])
        included |= new

    sub_nodes = {nid: n for nid, n in nodes.items() if nid in included}
    sub_edges = [e for e in edges if e["source"] in included and e["target"] in included]
    return sub_nodes, sub_edges


def render_html(nodes: dict, edges: list, output: str, title: str = "Knowledge Graph"):
    try:
        from pyvis.network import Network
    except ImportError:
        print("pyvis not installed. Run: uv pip install pyvis")
        return

    net = Network(height="850px", width="100%", bgcolor="#0d1b2a",
                  font_color="white", directed=True, notebook=False)
    net.set_options("""
    {
      "physics": {
        "barnesHut": {"gravitationalConstant": -8000, "springLength": 120},
        "stabilization": {"iterations": 300}
      },
      "nodes": {"borderWidth": 1.5, "shadow": {"enabled": true}},
      "edges": {
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.6}},
        "smooth": {"type": "dynamic"},
        "shadow": {"enabled": true}
      }
    }
    """)

    for nid, node in nodes.items():
        color = ENTITY_COLORS.get(node.get("type", ""), ENTITY_COLORS["default"])
        size = 8 + min(node.get("mentions", 1) * 1.5, 30)
        tooltip = (
            f"<b>{node.get('label', nid)}</b><br>"
            f"Type: {node.get('type', '?')}<br>"
            f"Mentions: {node.get('mentions', 0)}<br>"
            f"Papers: {node.get('paper_count', 0)}"
        )
        net.add_node(nid, label=node.get("label", nid),
                     title=tooltip, size=size, color=color)

    for edge in edges:
        color = RELATION_COLORS.get(edge.get("relation", ""), RELATION_COLORS["default"])
        width = 1 + min(edge.get("evidence_count", 1) * 0.5, 5)
        tooltip = (
            f"{edge.get('relation', 'RELATED_TO')}<br>"
            f"Evidence: {edge.get('evidence_count', 1)} papers<br>"
            f"Confidence: {edge.get('confidence', 0):.2f}"
        )
        net.add_edge(edge["source"], edge["target"],
                     title=tooltip,
                     label=edge.get("relation", ""),
                     color=color, width=width)

    Path(output).parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(output)
    print(f"Interactive graph saved: {output}")


def render_png(nodes: dict, edges: list, output: str, focus: str = None):
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("networkx/matplotlib not installed. Run: uv pip install networkx matplotlib")
        return

    G = nx.DiGraph()
    for nid, node in nodes.items():
        G.add_node(nid, **{k: v for k, v in node.items() if isinstance(v, (str, int, float))})
    for edge in edges:
        G.add_edge(edge["source"], edge["target"],
                   relation=edge.get("relation", ""),
                   weight=edge.get("evidence_count", 1))

    fig, ax = plt.subplots(figsize=(14, 10))
    ax.set_facecolor("#0d1b2a")
    fig.patch.set_facecolor("#0d1b2a")

    # Layout
    if len(G.nodes) <= 30:
        pos = nx.spring_layout(G, k=2, seed=42)
    else:
        pos = nx.kamada_kawai_layout(G)

    # Draw
    node_colors = [ENTITY_COLORS.get(nodes[n].get("type", ""), ENTITY_COLORS["default"])
                   for n in G.nodes]
    node_sizes = [100 + nodes[n].get("mentions", 1) * 50 for n in G.nodes]

    nx.draw_networkx_nodes(G, pos, node_color=node_colors,
                           node_size=node_sizes, alpha=0.9, ax=ax)
    nx.draw_networkx_labels(G, pos, font_size=7, font_color="white",
                            labels={n: nodes[n].get("label", n)[:15] for n in G.nodes}, ax=ax)

    edge_colors = [RELATION_COLORS.get(G[u][v]["relation"], RELATION_COLORS["default"])
                   for u, v in G.edges]
    nx.draw_networkx_edges(G, pos, edge_color=edge_colors, alpha=0.6,
                           arrows=True, arrowsize=10, ax=ax)

    # Legend
    legend_handles = [
        mpatches.Patch(color=color, label=etype)
        for etype, color in ENTITY_COLORS.items() if etype != "default"
        if any(nodes[n].get("type") == etype for n in G.nodes)
    ]
    ax.legend(handles=legend_handles, loc="upper left", fontsize=8,
              facecolor="#1a3a52", labelcolor="white", framealpha=0.8)

    title = f"Knowledge Graph" + (f" — {focus} (±{2} hops)" if focus else "")
    ax.set_title(title, color="white", fontsize=12, pad=10)
    ax.axis("off")

    plt.tight_layout()
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output, dpi=150, bbox_inches="tight", facecolor="#0d1b2a")
    print(f"PNG figure saved: {output}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--format", default="html", choices=["html", "png"])
    parser.add_argument("--focus-entity", default=None)
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--color-by", default="entity_type",
                        choices=["entity_type", "mentions"])
    args = parser.parse_args()

    nodes, edges = load_graph(args.graph)
    print(f"Loaded: {len(nodes)} nodes, {len(edges)} edges")

    if args.focus_entity:
        nodes, edges = get_subgraph(nodes, edges, args.focus_entity, args.hops)
        print(f"Subgraph: {len(nodes)} nodes, {len(edges)} edges")

    # Cap nodes for performance
    if len(nodes) > args.max_nodes:
        # Keep highest-mention nodes
        sorted_nodes = sorted(nodes.values(), key=lambda n: n.get("mentions", 0), reverse=True)
        keep_ids = {n["id"] for n in sorted_nodes[:args.max_nodes]}
        nodes = {nid: n for nid, n in nodes.items() if nid in keep_ids}
        edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
        print(f"Capped to {len(nodes)} nodes, {len(edges)} edges")

    if args.format == "html":
        render_html(nodes, edges, args.output)
    else:
        render_png(nodes, edges, args.output, args.focus_entity)


if __name__ == "__main__":
    main()
