#!/usr/bin/env python3
"""
Deduplicate raw systematic review results.

Usage:
    python scripts/deduplicate.py \
      --input results/raw_results.json \
      --output results/deduplicated.json

Requires: uv pip install rapidfuzz
"""

import json
import argparse
from pathlib import Path

def deduplicate(records: list) -> tuple[list, int]:
    """Deduplicate records, keeping the richest version of each paper."""
    # Source priority: pubmed > semantic_scholar > openalex > biorxiv_medrxiv
    SOURCE_PRIORITY = {"pubmed": 0, "semantic_scholar": 1, "openalex": 2, "biorxiv_medrxiv": 3}

    try:
        from rapidfuzz import fuzz
        use_fuzzy = True
    except ImportError:
        print("Warning: rapidfuzz not installed. Using exact title match only.")
        print("Install with: uv pip install rapidfuzz")
        use_fuzzy = False

    seen_dois = {}       # doi → index in unique_records
    seen_pmids = {}      # pmid → index
    unique_records = []
    n_duplicates = 0

    for record in records:
        doi = (record.get("doi") or "").strip().lower().replace("https://doi.org/", "")
        pmid = str(record.get("pmid") or "").strip()
        title = (record.get("title") or "").strip().lower()

        # Check DOI match
        if doi and doi in seen_dois:
            existing_idx = seen_dois[doi]
            existing = unique_records[existing_idx]
            # Keep higher priority source
            if SOURCE_PRIORITY.get(record["source"], 9) < SOURCE_PRIORITY.get(existing["source"], 9):
                # Merge: prefer higher-priority source but keep extra fields
                merged = {**record, **{k: v for k, v in existing.items() if not record.get(k)}}
                unique_records[existing_idx] = merged
            n_duplicates += 1
            continue

        # Check PMID match
        if pmid and pmid in seen_pmids:
            existing_idx = seen_pmids[pmid]
            n_duplicates += 1
            continue

        # Fuzzy title match
        if use_fuzzy and title:
            is_dup = False
            for i, existing in enumerate(unique_records):
                existing_title = (existing.get("title") or "").strip().lower()
                if existing_title and fuzz.token_sort_ratio(title, existing_title) > 92:
                    # Same year check for safety
                    if record.get("year") == existing.get("year") or not record.get("year"):
                        is_dup = True
                        n_duplicates += 1
                        # Merge abstract if missing
                        if not existing.get("abstract") and record.get("abstract"):
                            unique_records[i]["abstract"] = record["abstract"]
                        break
            if is_dup:
                continue

        # New unique record
        idx = len(unique_records)
        unique_records.append(record)
        if doi:
            seen_dois[doi] = idx
        if pmid:
            seen_pmids[pmid] = idx

    return unique_records, n_duplicates


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    records = data.get("records", data) if isinstance(data, dict) else data
    search_log = data.get("search_log", {}) if isinstance(data, dict) else {}

    print(f"Input records: {len(records)}")
    unique, n_dupes = deduplicate(records)
    print(f"Duplicates removed: {n_dupes}")
    print(f"Unique records: {len(unique)}")

    search_log["after_dedup"] = len(unique)
    search_log["duplicates_removed"] = n_dupes

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as f:
        json.dump({"search_log": search_log, "records": unique}, f, indent=2, default=str)

    print(f"Saved to {args.output}")


if __name__ == "__main__":
    main()
