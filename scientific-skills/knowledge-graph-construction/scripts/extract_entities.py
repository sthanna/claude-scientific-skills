#!/usr/bin/env python3
"""
Extract biomedical entities from paper abstracts/titles.

Two modes:
1. Rule-based (fast, no GPU): pattern matching + dictionaries
2. LLM-assisted (accurate, needs API key): structured extraction via Claude/GPT

Usage:
    # Rule-based
    python scripts/extract_entities.py \
      --input papers.json \
      --output entities.json

    # LLM-assisted (requires ANTHROPIC_API_KEY or OPENAI_API_KEY)
    python scripts/extract_entities.py \
      --input papers.json \
      --output entities.json \
      --mode llm \
      --model claude-3-5-sonnet-20241022

Requires: uv pip install spacy requests
"""

import json
import re
import os
import argparse
import time
from pathlib import Path
from collections import defaultdict

# ── Biomedical dictionaries ────────────────────────────────────────────────────
# Extend these with domain-specific terms

DRUG_PATTERNS = [
    r'\b(?:bedaquiline|delamanid|linezolid|rifampicin|isoniazid|pyrazinamide|ethambutol)\b',
    r'\b(?:ebselen|aspirin|metformin|ibuprofen|warfarin|penicillin|amoxicillin)\b',
    r'\bTMC\d+\b', r'\bABT-\d+\b', r'\bGSK\d+\b',
    r'\b[A-Z]{2,}-\d{3,}\b',  # e.g., AMB-101
    r'\b\w+-(?:umab|mab|nib|lib|zumab|ximab)\b',  # biologics
]

GENE_PROTEIN_PATTERNS = [
    r'\b(?:GlgE|InhA|KasA|KasB|MmpL3|DprE1|PanK|CoaBC)\b',
    r'\b(?:EGFR|BRAF|KRAS|TP53|BRCA1|BRCA2|HER2|ALK|ROS1|MET)\b',
    r'\b(?:TNF-?α|IL-?[0-9]+|IFN-?[γβα]|TGF-?β|NF-?κB)\b',
    r'\b[A-Z][a-z]?[A-Z][A-Za-z0-9]*(?:\d+)?\b',  # CamelCase genes
    r'\bp\d{2,}\b',  # p53, p21, p65
]

DISEASE_PATTERNS = [
    r'\b(?:tuberculosis|TB|Mycobacterium tuberculosis|MDR-TB|XDR-TB)\b',
    r'\b(?:Alzheimer\'?s?|Parkinson\'?s?|Huntington\'?s?)\b',
    r'\b(?:cancer|carcinoma|lymphoma|leukemia|sarcoma|melanoma|glioma)\b',
    r'\b(?:diabetes|hypertension|asthma|COPD|fibrosis)\b',
    r'\b(?:COVID-19|SARS-CoV-2|influenza|HIV|malaria|dengue)\b',
]

PATHWAY_PATTERNS = [
    r'\b(?:mTOR|PI3K|MAPK|Wnt|Notch|Hedgehog|JAK.STAT|NF-κB) (?:signaling|pathway)\b',
    r'\btrehalose (?:utilization|biosynthesis|metabolism)\b',
    r'\b(?:glycolysis|TCA cycle|oxidative phosphorylation|autophagy)\b',
    r'\b(?:apoptosis|necroptosis|pyroptosis|ferroptosis)\b',
    r'\b(?:cell cycle|DNA repair|DNA damage response)\b',
]

MECHANISM_PATTERNS = [
    r'\b(?:inhibit(?:ion|s|ed)|inhibitor)\b',
    r'\b(?:activat(?:ion|es|ed)|activator|agonist)\b',
    r'\b(?:bind(?:ing|s)|bound|binder)\b',
    r'\b(?:phosphorylat(?:ion|es|ed))\b',
    r'\b(?:upregulat|downregulat|overexpress)(?:ion|ed|es)\b',
    r'\b(?:antagonist|substrate|ligand|cofactor)\b',
]

ORGANISM_PATTERNS = [
    r'\b(?:Mycobacterium tuberculosis|M\. tuberculosis|MTB)\b',
    r'\b(?:Staphylococcus aureus|MRSA|S\. aureus)\b',
    r'\b(?:Aspergillus|Candida|Cryptococcus) \w+\b',
    r'\b(?:E\. coli|Escherichia coli)\b',
    r'\b(?:mouse|rat|murine|zebrafish|C\. elegans|Drosophila)\b',
]

COMPILED_PATTERNS = {
    "Drug": [re.compile(p, re.IGNORECASE) for p in DRUG_PATTERNS],
    "Gene/Protein": [re.compile(p, re.IGNORECASE) for p in GENE_PROTEIN_PATTERNS],
    "Disease": [re.compile(p, re.IGNORECASE) for p in DISEASE_PATTERNS],
    "Pathway": [re.compile(p, re.IGNORECASE) for p in PATHWAY_PATTERNS],
    "Mechanism": [re.compile(p, re.IGNORECASE) for p in MECHANISM_PATTERNS],
    "Organism": [re.compile(p, re.IGNORECASE) for p in ORGANISM_PATTERNS],
}


def extract_rule_based(text: str, entity_types: list = None) -> list:
    """Extract entities from text using rule-based patterns."""
    if not text:
        return []
    entities = []
    types_to_check = entity_types or list(COMPILED_PATTERNS.keys())
    for etype, patterns in COMPILED_PATTERNS.items():
        if etype not in types_to_check:
            continue
        for pattern in patterns:
            for match in pattern.finditer(text):
                entities.append({
                    "text": match.group().strip(),
                    "type": etype,
                    "start": match.start(),
                    "end": match.end(),
                    "method": "rule_based",
                    "confidence": 0.7,
                })
    return entities


def deduplicate_entities(entities: list) -> list:
    """Merge duplicate entity mentions."""
    seen = {}
    for e in entities:
        key = (e["text"].lower(), e["type"])
        if key not in seen:
            seen[key] = {**e, "count": 1, "aliases": set([e["text"]])}
        else:
            seen[key]["count"] += 1
            seen[key]["aliases"].add(e["text"])

    result = []
    for item in seen.values():
        item["aliases"] = list(item["aliases"])
        result.append(item)
    return sorted(result, key=lambda x: x["count"], reverse=True)


# ── LLM extraction ─────────────────────────────────────────────────────────────

LLM_PROMPT = """Extract all biomedical entities from this scientific text.
Return a JSON array of objects with fields: "text", "type", "confidence" (0-1).

Entity types to extract:
- Drug: small molecules, biologics, compounds (include IDs like IC50 values if mentioned)
- Gene/Protein: genes, proteins, enzymes (include organism if specified)
- Disease: diseases, conditions, syndromes
- Pathway: biological pathways, cellular processes
- Mechanism: modes of action (inhibition, activation, binding, etc.)
- Organism: bacterial species, model organisms, pathogens
- Assay: experimental methods, measurement techniques

Text:
{text}

Return ONLY valid JSON array, no other text."""


def extract_llm(texts: list, model: str = "claude-3-5-sonnet-20241022") -> list:
    """Extract entities using LLM. Returns list of entity lists (one per text)."""
    results = []

    if "claude" in model.lower():
        import anthropic
        client = anthropic.Anthropic()

        for text in texts:
            if not text or len(text) < 20:
                results.append([])
                continue
            try:
                msg = client.messages.create(
                    model=model,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": LLM_PROMPT.format(text=text[:2000])}]
                )
                entities = json.loads(msg.content[0].text)
                results.append(entities)
            except Exception as e:
                print(f"  LLM extraction error: {e}")
                results.append(extract_rule_based(text))
            time.sleep(0.1)

    elif "gpt" in model.lower():
        import openai
        client = openai.OpenAI()

        for text in texts:
            if not text or len(text) < 20:
                results.append([])
                continue
            try:
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": LLM_PROMPT.format(text=text[:2000])}],
                    response_format={"type": "json_object"}
                )
                raw = json.loads(resp.choices[0].message.content)
                entities = raw if isinstance(raw, list) else raw.get("entities", [])
                results.append(entities)
            except Exception as e:
                print(f"  LLM extraction error: {e}")
                results.append(extract_rule_based(text))
            time.sleep(0.05)

    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--mode", default="rule_based", choices=["rule_based", "llm"])
    parser.add_argument("--model", default="claude-3-5-sonnet-20241022")
    parser.add_argument("--types", nargs="+",
                        default=["Drug", "Gene/Protein", "Disease", "Pathway", "Mechanism", "Organism"])
    parser.add_argument("--batch-size", type=int, default=50)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)
    papers = data if isinstance(data, list) else data.get("records", [])

    print(f"Processing {len(papers)} papers in {args.mode} mode...")

    paper_entities = []

    if args.mode == "rule_based":
        for p in papers:
            text = f"{p.get('title', '')} {p.get('abstract', '')}"
            entities = extract_rule_based(text, args.types)
            if entities:
                paper_entities.append({
                    "paper_doi": p.get("doi"),
                    "paper_title": p.get("title"),
                    "year": p.get("year"),
                    "entities": deduplicate_entities(entities)
                })
    else:
        texts = [f"{p.get('title', '')} {p.get('abstract', '')}" for p in papers]
        for i in range(0, len(texts), args.batch_size):
            batch_texts = texts[i:i + args.batch_size]
            batch_papers = papers[i:i + args.batch_size]
            batch_results = extract_llm(batch_texts, args.model)
            for p, entities in zip(batch_papers, batch_results):
                if entities:
                    paper_entities.append({
                        "paper_doi": p.get("doi"),
                        "paper_title": p.get("title"),
                        "year": p.get("year"),
                        "entities": entities
                    })
            print(f"  Processed {min(i + args.batch_size, len(papers))}/{len(papers)}")

    # Global entity index
    global_entities = defaultdict(lambda: {"type": "", "mentions": 0, "papers": [], "aliases": set()})
    for pe in paper_entities:
        for e in pe["entities"]:
            key = e["text"].lower()
            global_entities[key]["type"] = e.get("type", "Unknown")
            global_entities[key]["mentions"] += e.get("count", 1)
            global_entities[key]["aliases"].add(e["text"])
            doi = pe.get("paper_doi")
            if doi and doi not in global_entities[key]["papers"]:
                global_entities[key]["papers"].append(doi)

    # Convert sets to lists for JSON serialization
    for key in global_entities:
        global_entities[key]["aliases"] = list(global_entities[key]["aliases"])
        global_entities[key]["id"] = key

    output = {
        "total_papers": len(papers),
        "papers_with_entities": len(paper_entities),
        "global_entities": dict(global_entities),
        "paper_entities": paper_entities
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    print(f"\nExtracted {len(global_entities)} unique entities from {len(paper_entities)} papers")
    print(f"Saved to {args.output}")

    # Print top entities
    top = sorted(global_entities.values(), key=lambda x: x["mentions"], reverse=True)[:10]
    print("\nTop 10 entities:")
    for e in top:
        print(f"  [{e['type']}] {e['id']} — {e['mentions']} mentions, {len(e['papers'])} papers")


if __name__ == "__main__":
    main()
