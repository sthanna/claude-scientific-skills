# Bibliometric Metrics Reference

## Author-Level Metrics

### h-index
**Definition**: The largest number h such that h papers have each been cited ≥ h times.
**Interpretation**: h=20 means at least 20 papers each cited at least 20 times.
**Strength**: Balances productivity and impact; hard to game.
**Weakness**: Grows with career length; disadvantages early-career researchers.

```python
def h_index(citation_counts: list) -> int:
    sorted_cites = sorted(citation_counts, reverse=True)
    return sum(1 for i, c in enumerate(sorted_cites) if c >= i + 1)
```

### g-index
**Definition**: Largest g where top g papers have g² total citations.
**Better than h for**: Identifying researchers with a few very highly cited papers.

```python
def g_index(citation_counts: list) -> int:
    sorted_cites = sorted(citation_counts, reverse=True)
    cumsum, g = 0, 0
    for i, c in enumerate(sorted_cites):
        cumsum += c
        if cumsum >= (i + 1) ** 2:
            g = i + 1
    return g
```

### m-index (m-quotient)
**Definition**: h-index / years since first publication
**Use**: Comparing researchers at different career stages.
**Benchmark**: m > 1 = very good; m > 2 = excellent; m > 3 = exceptional

### i10-index
**Definition**: Number of papers with ≥10 citations.
**Used by**: Google Scholar. Simple breadth measure.

### Citation rate (velocity)
**Definition**: Total citations / career years (or per year of publication)
**Use**: Identifies high-impact recent work vs. legacy citations.

---

## Field/Journal Metrics

### Journal h-index (in field)
The h-index computed only for papers from that journal within the specific research topic. More meaningful than impact factor for niche fields.

### Citation density
Total citations / total papers in corpus. Use to compare how "hot" a field is.

---

## Paper-Level Signals

### Citation burst
Papers gaining citations significantly faster than field average. Formula:
```python
burst_score = citation_rate_per_year / field_avg_citation_rate
# burst_score > 3.0 = notable burst
```

### Sleeping beauty
Papers with very low initial citations (< 5 citations/year for 5+ years) followed by rapid growth. Indicates delayed recognition of pioneering work.

### Field founder
Age ≥ 5 years + citations > 100 + citation rate > field average × 2.

---

## Pharmaceutical/Biomedical Benchmarks

### h-index by career stage (drug discovery/medicinal chemistry)
| Career Stage | Typical h-index |
|---|---|
| PhD student (5 yr) | 2–6 |
| Postdoc (2–4 yr post-PhD) | 5–12 |
| Junior scientist / industry (5–10 yr) | 8–20 |
| Senior scientist (10–15 yr) | 15–35 |
| Principal scientist / director | 25–60 |
| Top academic PI | 40–100+ |

Note: Industrial scientists often have lower h-index than academics due to proprietary work and fewer publications, but higher patent counts.

### Influential journals (by field)

**Medicinal Chemistry / Drug Discovery**
- Journal of Medicinal Chemistry (IF ~7)
- ACS Medicinal Chemistry Letters (IF ~4)
- European Journal of Medicinal Chemistry (IF ~6)
- Bioorganic & Medicinal Chemistry (IF ~4)
- ChemMedChem (IF ~4)

**Vaccine Development / Immunology**
- npj Vaccines (IF ~7)
- Vaccine (IF ~5)
- Journal of Infectious Diseases (IF ~6)
- The Lancet Infectious Diseases (IF ~36)

**Organic / Synthetic Chemistry**
- Journal of the American Chemical Society (IF ~15)
- Angewandte Chemie (IF ~16)
- Organic Letters (IF ~6)
- Journal of Organic Chemistry (IF ~4)

**Pharmaceutical Sciences / ADMET**
- European Journal of Pharmaceutics
- Journal of Pharmaceutical Sciences
- Molecular Pharmaceutics

---

## Interpreting Co-authorship Networks

- **Hubs**: High-degree nodes = highly collaborative researchers. Often senior PIs or industry leads.
- **Bridges**: Nodes connecting otherwise separate clusters = cross-disciplinary collaborators. High betweenness centrality.
- **Isolated clusters**: Separate research groups working in silos.
- **Dense clusters**: Active collaboration within a lab or institution.

Key NetworkX centrality measures for authors:
```python
import networkx as nx

G = nx.Graph()
# Add nodes/edges from co-authorship data

degree_cent = nx.degree_centrality(G)        # local connectivity
betweenness = nx.betweenness_centrality(G)   # bridge score
eigenvector = nx.eigenvector_centrality(G)   # connected to well-connected = influence
pagerank = nx.pagerank(G)                    # citation-like influence
```

---

## Keyword Co-occurrence Interpretation

- **Large, central keywords**: Core concepts of the field.
- **Tightly clustered keywords**: Sub-fields or methodological approaches.
- **Peripheral emerging keywords**: New research directions growing at field edges.
- **Isolated keywords**: Niche topics with few cross-topic connections.

To detect emerging topics: compare keyword frequency in 2019–2021 vs. 2022–2024. Keywords with growth rate > 200% are "emerging."
