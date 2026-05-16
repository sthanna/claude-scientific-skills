---
name: systematic-review-automation
description: >
  Automate systematic literature review workflows - screening thousands of papers,
  applying PICO/SPIDER inclusion/exclusion criteria, deduplicating results, scoring
  relevance, generating PRISMA flow diagrams, and producing evidence tables.
  Use when: (1) screening large sets of papers (100-100k) for a systematic review
  or meta-analysis, (2) applying structured inclusion/exclusion criteria at scale,
  (3) building PRISMA-compliant search documentation, (4) extracting structured data
  from paper abstracts/titles for evidence tables, (5) any task mentioning systematic
  review, PRISMA, PICO framework, paper screening, or meta-analysis automation.
  Significantly more powerful than the generic literature-review skill - designed
  for pharmaceutical, clinical, and life-science systematic reviews with domain-aware
  screening logic.
license: MIT
---

# Systematic Review Automation

Automate the most time-consuming parts of a systematic review: multi-database harvesting, deduplication, relevance scoring, and PRISMA-compliant reporting. Designed for the scale of real pharmaceutical and clinical research (thousands to tens of thousands of papers).

## Core Workflow

```
Define PICO/SPIDER → Search databases → Deduplicate → Title/Abstract screen
→ Full-text eligibility → Data extraction → PRISMA diagram → Evidence table
```

Read `references/databases.md` for API endpoints, rate limits, and field mappings.
Read `references/screening-criteria.md` for PICO/SPIDER templates and scoring logic.

## Phase 1: Search Strategy

### PICO Framework (RCTs, clinical, drug)
```
P – Population/Problem: e.g., "patients with treatment-resistant tuberculosis"
I – Intervention: e.g., "bedaquiline OR delamanid"
C – Comparison: e.g., "standard DOTS regimen"
O – Outcome: e.g., "sputum conversion OR treatment success"
```

### SPIDER Framework (qualitative/mixed methods)
```
S – Sample, PI – Phenomenon of Interest, D – Design, E – Evaluation, R – Research type
```

### Boolean search construction
```python
# Combine with AND/OR/NOT, use MeSH terms + free text
query = (
    '("bedaquiline" OR "TMC207") AND '
    '("tuberculosis" OR "TB" OR "Mycobacterium tuberculosis") AND '
    '("randomized controlled trial" OR "RCT" OR "clinical trial")'
)
```

## Phase 2: Multi-Database Harvest

Run `scripts/harvest.py` to pull from all sources in one command:

```bash
python scripts/harvest.py \
  --query "your boolean query here" \
  --databases pubmed openalex biorxiv semantic_scholar \
  --max-per-db 2000 \
  --output results/raw_results.json
```

Supported databases and their strengths:
| Database | Best for | Free API |
|---|---|---|
| PubMed | Clinical, biomedical (MEDLINE) | Yes |
| OpenAlex | 240M+ papers, citations, OA | Yes |
| bioRxiv/medRxiv | Latest preprints | Yes |
| Semantic Scholar | CS + biomed + full text links | Yes (key recommended) |
| Embase | Drug studies, pharmacology | Institutional access |
| Cochrane | Systematic reviews, RCTs | Institutional access |

## Phase 3: Deduplication

```bash
python scripts/deduplicate.py \
  --input results/raw_results.json \
  --output results/deduplicated.json \
  --match-fields title doi pmid
```

Uses fuzzy title matching (threshold 0.92) + DOI exact match + PMID exact match.
Reports: total retrieved, duplicates removed, unique records.

## Phase 4: Screening

### Title/Abstract screen (AI-assisted)

```bash
python scripts/screen.py \
  --input results/deduplicated.json \
  --criteria references/screening-criteria.md \
  --output results/screened.json \
  --confidence-threshold 0.7
```

Each record gets:
- `decision`: include / exclude / uncertain
- `confidence`: 0.0–1.0
- `reason`: which criterion triggered

**Manual review queue**: Records with `confidence < 0.7` or `decision = uncertain` are flagged for human review.

### Full-text eligibility

For records passing title/abstract: retrieve full text (PubMed Central, Unpaywall, Semantic Scholar) and apply stricter criteria. Update `screened.json` with `full_text_decision`.

## Phase 5: Data Extraction

```bash
python scripts/extract.py \
  --input results/screened.json \
  --template references/extraction-template.md \
  --output results/evidence_table.csv
```

Standard extraction fields (pharmaceutical focus):
- Study design, sample size, population, intervention dose/duration
- Primary outcome, effect size (OR/RR/HR), 95% CI, p-value
- Risk of bias (RoB 2, GRADE), funding source, conflicts of interest

## Phase 6: PRISMA Flow Diagram

```bash
python scripts/prisma_diagram.py \
  --log results/prisma_log.json \
  --output figures/prisma_flow.png
```

Auto-populated from harvest/dedup/screen logs. Generates publication-ready PNG.

PRISMA counts captured automatically:
- Records identified per database
- Duplicates removed
- Records screened / excluded (title/abstract)
- Full texts assessed / excluded (with reasons)
- Studies included in synthesis

## Phase 7: Evidence Table & Report

```bash
python scripts/generate_report.py \
  --evidence results/evidence_table.csv \
  --prisma figures/prisma_flow.png \
  --output review_report.md \
  --format markdown   # or pdf
```

## Key Principles

**Reproducibility**: Every search is logged with date, query string, database version, and result count. Store in `results/search_log.json`.

**Dual screening**: For publication-quality reviews, flag all uncertain records and use a second reviewer for conflicts. Log inter-rater agreement (Cohen's kappa target: >0.8).

**GRADE evidence quality**: Assess each outcome across included studies — risk of bias, inconsistency, indirectness, imprecision, publication bias.

**Pharmaceutical-specific checks**:
- Phase of clinical trial (I/II/III/IV)
- Regulatory context (IND, NDA, EMA)
- Bioconjugate/CMC relevance for vaccine papers
- Off-target effects, ADMET data availability

## Integration with other skills

- `pubmed-database` / `openalex-database` — primary data sources
- `bgpt-paper-search` — structured full-text extraction (25+ fields per paper)
- `literature-review` — narrative synthesis after systematic screening
- `scientific-writing` — manuscript preparation
- `citation-management` — export to Zotero/Mendeley

## References

- `references/databases.md` — API details, field mappings, rate limits for each database
- `references/screening-criteria.md` — PICO/SPIDER templates, inclusion/exclusion logic, GRADE
