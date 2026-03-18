---
name: bibliometric-analysis
description: >
  Map the landscape of a research field using bibliometric analysis - identifying
  most influential authors, papers, journals, institutions, and emerging research
  trends. Produces co-authorship networks, citation burst detection, keyword co-occurrence
  maps, h-index benchmarks, and journal impact profiles. Use when: (1) understanding
  the intellectual structure of a field, (2) identifying key players and gatekeepers,
  (3) tracking how a research topic has evolved over time, (4) comparing author or
  institution output/impact, (5) any task mentioning bibliometrics, citation analysis,
  co-authorship network, research landscape, h-index, impact factor, or field mapping.
  Covers pharmaceutical, biomedical, chemistry, and interdisciplinary domains.
license: MIT
---

# Bibliometric Analysis

Map research field landscapes: who's influential, what's trending, how ideas cluster, and where the field is heading. Combines OpenAlex's 240M+ paper database with network analysis.

## Quick Start

```bash
# Full field analysis in one command
python scripts/analyze.py \
  --topic "glycoconjugate vaccine development" \
  --years 2015 2024 \
  --email your@email.com \
  --output results/
```

Produces: top authors, top papers, top journals, co-authorship network, keyword trends, and a summary report.

## Core Analyses

### 1. Author Impact Analysis

**Metrics computed per author**: h-index, total citations, papers count, citation rate/year, institutional affiliation, active years.

```python
# See scripts/author_metrics.py
python scripts/analyze.py --topic "CRISPR therapeutics" --mode authors --top-n 20
```

Output includes:
- Ranked author table with h-index, citations, paper count
- Career trajectory plot (papers/year, citations/year)
- Institutional affiliation breakdown
- Collaboration network (who works with whom)

### 2. Paper Impact & Citation Burst Detection

Identify breakthrough papers: sudden spikes in citations signal emerging paradigm shifts.

```python
python scripts/analyze.py --topic "mRNA vaccines" --mode papers --top-n 50
```

Detects:
- **Citation bursts**: papers gaining citations faster than field average
- **Sleeping beauties**: papers with delayed recognition (low → high citations)
- **Field founders**: earliest high-cited papers (>5 years old, >100 citations)

### 3. Journal Landscape

```python
python scripts/analyze.py --topic "medicinal chemistry SAR" --mode journals
```

Output: journal ranking by total field papers, citations, avg citations/paper, OA percentage, h-index of journal in this topic.

### 4. Co-authorship Network

```python
python scripts/network.py \
  --input results/papers.json \
  --mode coauthorship \
  --min-papers 3 \
  --output results/coauthor_network.html
```

Interactive HTML network (uses pyvis). Nodes = authors, edges = collaborations, size = h-index, color = institution.

### 5. Keyword Co-occurrence & Topic Evolution

```python
python scripts/network.py \
  --input results/papers.json \
  --mode keywords \
  --output results/keyword_map.html
```

Shows which concepts cluster together and tracks keyword frequency over years to reveal emerging vs. declining topics.

### 6. Institutional & Country Analysis

```python
python scripts/analyze.py --topic "vaccine adjuvants" --mode institutions
```

Output: country map of research output, top institutions by papers and citations, industry vs. academia split.

## Key Metrics Reference

| Metric | Definition | Good for |
|---|---|---|
| h-index | Largest h where author has h papers with ≥h citations | Author impact |
| g-index | Largest g where top g papers have ≥g² total citations | Top-paper focus |
| m-index | h-index / career years | Normalized for career stage |
| i10-index | Papers with ≥10 citations | Breadth of contribution |
| Citation rate | Citations per year | Recency-corrected impact |

## Pharmaceutical Field Benchmarks

Typical h-index ranges (active career, 15+ years):
- Junior PI (10 yr): h = 15–25
- Senior PI / Director: h = 30–60
- Top field leaders: h = 60–100+

For context: Sandeep Thanna's profile (h=9, 390+ citations, 12+ papers, 14 years career) is consistent with a high-output mid-career industrial scientist in medicinal chemistry / vaccine development.

## Output Files

```
results/
├── papers.json              — all fetched papers with metadata
├── authors_top20.csv        — ranked author table
├── journals_ranking.csv     — journal landscape
├── keyword_trends.csv       — keyword frequency by year
├── coauthor_network.html    — interactive network
├── keyword_map.html         — keyword co-occurrence map
└── report.md                — narrative summary
```

## Dependencies

```bash
uv pip install requests pandas networkx pyvis matplotlib plotly
```

## Integration with other skills

- `openalex-database` — primary data source (240M+ papers, free, no auth)
- `networkx` — graph algorithms for network centrality analysis
- `systematic-review-automation` — use bibliometric scoping first, then systematic review
- `knowledge-graph-construction` — extend bibliometric map into a full concept graph
- `scientific-writing` — incorporate findings into manuscript introduction/background

## References

- `references/metrics.md` — complete metric definitions, interpretation guides, benchmarks
- `references/openalex-fields.md` — OpenAlex field names, concept hierarchy, filter syntax
