#!/usr/bin/env python3
"""
Build a knowledge graph from extracted entities and relations.
Outputs a JSON graph + optional GraphML for Cytoscape/Gephi.

Usage:
    python scripts/build_graph.py \
      --entities entities.json \
      --relations relations.json \
      --output results/knowledge_graph.json

    python scripts/build_graph.py \
      --entities entities.json \
      --output results/knowledge_graph.json  # entities only, infer co-occurrence edges

Requires: uv pip install networkx
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict


def build_graph(entities_data: dict, relations_data: list = None,
                min_entity_mentions: int = 1) -> dict:
    """Build graph from entities and optional relations."""

    # Nodes from global entities
    nodes = {}
    for eid, edata in entities_data.get("global_entities", {}).items():
        if edata["mentions"] < min_entity_mentions:
            continue
        nodes[eid] = {
            "id": eid,
            "label": edata["aliases"][0] if edata["aliases"] else eid,
            "type": edata["type"],
            "mentions": edata["mentions"],
            "paper_count": len(edata["papers"]),
            "aliases": edata["aliases"],
            "papers": edata["papers"],
        }

    # Edges from explicit relations
    edges = []
    edge_index = defaultdict(list)

    if relations_data:
        for rel in relations_data:
            src = rel.get("source", "").lower()
            tgt = rel.get("target", "").lower()
            if src in nodes and tgt in nodes:
                edge_key = (src, tgt, rel.get("relation", "RELATED_TO"))
                edge_index[edge_key].append(rel)

        for (src, tgt, rtype), evidence in edge_index.items():
            edges.append({
                "source": src,
                "target": tgt,
                "relation": rtype,
                "confidence": sum(e.get("confidence", 0.5) for e in evidence) / len(evidence),
                "evidence_count": len(evidence),
                "supporting_sentences": [e.get("sentence", "") for e in evidence[:3]],
                "papers": list({e.get("doi", "") for e in evidence if e.get("doi")}),
            })

    # Co-occurrence edges (entities co-mentioned in same paper)
    paper_to_entities = defaultdict(list)
    for eid, edata in entities_data.get("global_entities", {}).items():
        if eid not in nodes:
            continue
        for doi in edata.get("papers", []):
            paper_to_entities[doi].append(eid)

    co_occur = defaultdict(int)
    co_occur_papers = defaultdict(set)
    for doi, ents in paper_to_entities.items():
        for i in range(len(ents)):
            for j in range(i + 1, len(ents)):
                pair = tuple(sorted([ents[i], ents[j]]))
                co_occur[pair] += 1
                co_occur_papers[pair].add(doi)

    # Only add co-occurrence edges not already covered by explicit relations
    existing_edge_pairs = {(e["source"], e["target"]) for e in edges}
    existing_edge_pairs |= {(e["target"], e["source"]) for e in edges}

    for (e1, e2), count in co_occur.items():
        if count < 2:  # require at least 2 papers for co-occurrence edge
            continue
        if (e1, e2) in existing_edge_pairs:
            continue
        edges.append({
            "source": e1,
            "target": e2,
            "relation": "CO_MENTIONED",
            "confidence": min(0.3 + count * 0.1, 0.8),
            "evidence_count": count,
            "papers": list(co_occur_papers[(e1, e2)])[:5],
        })

    graph = {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "n_nodes": len(nodes),
            "n_edges": len(edges),
            "n_explicit_relations": len([e for e in edges if e["relation"] != "CO_MENTIONED"]),
            "n_cooccurrence_edges": len([e for e in edges if e["relation"] == "CO_MENTIONED"]),
            "entity_types": list({n["type"] for n in nodes.values()}),
        }
    }

    return graph


def to_graphml(graph: dict, output: str):
    """Export graph to GraphML format for Cytoscape/Gephi."""
    try:
        import networkx as nx
        G = nx.DiGraph()
        for node in graph["nodes"]:
            G.add_node(node["id"],
                      label=node["label"],
                      entity_type=node["type"],
                      mentions=node["mentions"],
                      paper_count=node["paper_count"])
        for edge in graph["edges"]:
            G.add_edge(edge["source"], edge["target"],
                      relation=edge["relation"],
                      confidence=edge["confidence"],
                      evidence_count=edge["evidence_count"])
        nx.write_graphml(G, output)
        print(f"  GraphML saved: {output}")
    except ImportError:
        print("networkx not installed. Run: uv pip install networkx")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--entities", required=True)
    parser.add_argument("--relations", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--min-mentions", type=int, default=1)
    parser.add_argument("--export-graphml", action="store_true")
    args = parser.parse_args()

    with open(args.entities) as f:
        entities_data = json.load(f)

    relations_data = None
    if args.relations:
        with open(args.relations) as f:
            relations_data = json.load(f)
        if isinstance(relations_data, dict):
            relations_data = relations_data.get("relations", [])

    print("Building knowledge graph...")
    graph = build_graph(entities_data, relations_data, args.min_mentions)

    stats = graph["stats"]
    print(f"  Nodes: {stats['n_nodes']}")
    print(f"  Edges: {stats['n_edges']} ({stats['n_explicit_relations']} explicit, {stats['n_cooccurrence_edges']} co-occurrence)")
    print(f"  Entity types: {', '.join(stats['entity_types'])}")

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(graph, f, indent=2, default=str)
    print(f"  Graph saved: {args.output}")

    if args.export_graphml:
        graphml_path = args.output.replace(".json", ".graphml")
        to_graphml(graph, graphml_path)


if __name__ == "__main__":
    main()
