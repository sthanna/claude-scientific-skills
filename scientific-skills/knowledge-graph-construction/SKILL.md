---
name: knowledge-graph-construction
description: >
  Build knowledge graphs from scientific papers - extracting entities (genes, drugs,
  diseases, mechanisms, compounds), relations (inhibits, targets, causes, binds),
  and connecting them into a queryable graph. Produces visual concept maps, entity
  relationship tables, and exportable graph formats (JSON-LD, GraphML, RDF).
  Use when: (1) connecting facts across many papers into a unified concept network,
  (2) discovering indirect relationships between entities (e.g., drug A affects pathway B
  which modulates disease C), (3) building a structured knowledge base from unstructured
  literature, (4) any task mentioning knowledge graph, entity extraction, relation extraction,
  concept map, RDF, ontology, NER on papers, or literature-to-graph workflows.
  Domain-optimized for pharmaceutical, biomedical, and vaccine research (supports
  drug-target, disease-gene, compound-mechanism entity types out of the box).
license: MIT
---

# Knowledge Graph Construction

Extract structured knowledge from scientific papers and connect it into a navigable, queryable graph. Goes beyond search — reveals indirect paths like "compound X → inhibits → enzyme Y → regulates → pathway Z → implicated in → disease W."

## Core Workflow

```
Collect papers → Extract entities → Extract relations → Merge/deduplicate
→ Build graph → Query/visualize → Export
```

Read `references/entity-types.md` for full taxonomy and extraction patterns.
Read `references/ontologies.md` for biomedical ontology mappings (MeSH, ChEBI, GO, HPO).

## Phase 1: Entity Extraction

### Supported entity types (biomedical/pharma focus)

| Type | Examples | Ontology |
|---|---|---|
| Drug / Compound | bedaquiline, TMC207, ebselen | ChEBI, DrugBank |
| Gene / Protein | GlgE, InhA, EGFR, TNF-α | UniProt, HGNC |
| Disease | tuberculosis, Alzheimer's, lung cancer | MeSH, OMIM, DO |
| Pathway | trehalose utilization, mTOR signaling | KEGG, Reactome |
| Mechanism | inhibition, activation, binding, phosphorylation | GO Molecular Function |
| Cell type | macrophage, T-cell, neutrophil | CL ontology |
| Organism | M. tuberculosis, S. aureus, SARS-CoV-2 | NCBI Taxonomy |
| Modification | N-glycosylation, methylation, acetylation | MOD ontology |
| Assay / Method | IC50, MIC, Ki, SPR, MALDI-TOF | OBCI |

### Rule-based extraction (no GPU needed)

```bash
python scripts/extract_entities.py \
  --input papers.json \
  --output entities.json \
  --types drug gene disease pathway mechanism
```

Uses pattern matching + biomedical dictionaries. Fast and reproducible.

### LLM-assisted extraction (higher recall/precision)

```bash
python scripts/extract_entities.py \
  --input papers.json \
  --output entities.json \
  --mode llm \
  --model claude-3-5-sonnet  # or gpt-4o
```

Each abstract is sent to the LLM with a structured prompt. Returns typed entities + confidence scores.

## Phase 2: Relation Extraction

Extract semantic relationships between entities:

```bash
python scripts/extract_relations.py \
  --entities entities.json \
  --papers papers.json \
  --output relations.json
```

**Core relation types**:
- `INHIBITS` / `ACTIVATES` / `BINDS` (compound → target)
- `CAUSES` / `ASSOCIATED_WITH` (variant/mutation → disease)
- `TARGETS` (drug → gene/protein)
- `UPREGULATES` / `DOWNREGULATES` (gene → gene)
- `PART_OF` / `REGULATES` (gene → pathway)
- `TREATS` / `INDICATED_FOR` (drug → disease)
- `MEASURED_BY` (entity → assay)

Each relation includes: source entity, target entity, relation type, confidence, supporting sentence, paper DOI.

## Phase 3: Build the Graph

```bash
python scripts/build_graph.py \
  --entities entities.json \
  --relations relations.json \
  --output results/knowledge_graph.json \
  --deduplicate-threshold 0.85
```

Graph structure:
- **Nodes**: entities, typed and normalized to ontology IDs where possible
- **Edges**: relations with provenance (paper, sentence, confidence)
- **Metadata**: entity aliases, ontology mappings, paper count per entity

## Phase 4: Query the Graph

```python
from scripts.query_graph import KnowledgeGraph

kg = KnowledgeGraph("results/knowledge_graph.json")

# Find all drugs that inhibit a gene involved in a disease
paths = kg.find_paths(
    source_type="Drug",
    target="tuberculosis",
    max_hops=3,
    via_relations=["INHIBITS", "TARGETS", "ASSOCIATED_WITH"]
)

# Get all relations for a specific entity
ebselen_rels = kg.entity_relations("ebselen")

# Find entities co-mentioned with a compound
co_entities = kg.co_occurrences("bedaquiline", min_papers=2)

# Shortest path between two entities
path = kg.shortest_path("bedaquiline", "M. tuberculosis")
```

## Phase 5: Visualize

```bash
python scripts/visualize.py \
  --graph results/knowledge_graph.json \
  --output results/kg_visualization.html \
  --max-nodes 200 \
  --color-by entity_type
```

Interactive HTML network (pyvis). Node size = mention frequency; color = entity type; edge thickness = evidence count.

For publication figures:
```bash
python scripts/visualize.py \
  --graph results/knowledge_graph.json \
  --output results/kg_figure.png \
  --format png \
  --focus-entity "bedaquiline" \
  --hops 2
```

## Phase 6: Export

```bash
# GraphML (Cytoscape, Gephi)
python scripts/export.py --graph results/knowledge_graph.json --format graphml --output kg.graphml

# RDF/Turtle (semantic web)
python scripts/export.py --graph results/knowledge_graph.json --format rdf --output kg.ttl

# CSV edge list (Excel, pandas)
python scripts/export.py --graph results/knowledge_graph.json --format csv --output kg_edges.csv
```

## Pharmaceutical Use Cases

**Drug repurposing**: Find drugs targeting genes associated with a new disease.
```python
paths = kg.find_paths("Drug", "COVID-19", via=["TARGETS", "ASSOCIATED_WITH"])
```

**Mechanism of action mapping**: Trace a compound's effects through intermediary proteins.
```python
kg.find_paths("ebselen", "neuroprotection", max_hops=4)
```

**Adverse effect discovery**: Link drugs to unexpected biological pathways.
```python
kg.co_occurrences("compound_X", entity_type="Pathway", min_papers=3)
```

**Vaccine target identification**: Find surface proteins associated with protective immunity.
```python
kg.find_paths("protective_immunity", "surface_protein", via=["ASSOCIATED_WITH", "EXPRESSED_BY"])
```

## Dependencies

```bash
uv pip install networkx pyvis requests spacy pandas
python -m spacy download en_core_web_sm  # basic NER
# For biomedical NER:
uv pip install scispacy
python -m pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz
```

## Integration

- `systematic-review-automation` — feed screened papers as graph input
- `bibliometric-analysis` — use top papers as graph seed
- `networkx` — advanced graph algorithms (centrality, community detection, path finding)
- `pubmed-database` / `openalex-database` — paper data sources

## References

- `references/entity-types.md` — full entity taxonomy, extraction patterns, pharma-specific types
- `references/ontologies.md` — ontology IDs, normalization strategies, ChEBI/MeSH/GO mappings
