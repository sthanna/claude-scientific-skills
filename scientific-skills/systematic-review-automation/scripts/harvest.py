#!/usr/bin/env python3
"""
Multi-database literature harvester for systematic reviews.

Usage:
    python scripts/harvest.py \
      --query '"bedaquiline" AND "tuberculosis" AND "clinical trial"' \
      --databases pubmed openalex biorxiv semantic_scholar \
      --max-per-db 2000 \
      --email your@email.com \
      --output results/raw_results.json
"""

import json
import time
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ── PubMed ─────────────────────────────────────────────────────────────────────

def search_pubmed(query: str, max_results: int = 2000, api_key: str = None) -> list:
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    headers = {}
    params = {
        "db": "pubmed", "term": query,
        "retmax": min(max_results, 9999),
        "retmode": "json", "usehistory": "y"
    }
    if api_key:
        params["api_key"] = api_key

    r = requests.get(base + "esearch.fcgi", params=params, timeout=30)
    r.raise_for_status()
    data = r.json()["esearchresult"]
    ids = data.get("idlist", [])
    count = int(data.get("count", 0))
    print(f"  PubMed: found {count}, fetching {len(ids)}")

    if not ids:
        return []

    # Fetch abstracts
    records = []
    batch_size = 200
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        r2 = requests.post(
            base + "efetch.fcgi",
            data={"db": "pubmed", "id": ",".join(batch), "retmode": "xml"},
            timeout=60
        )
        # Parse XML minimally
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r2.text)
        for article in root.findall(".//PubmedArticle"):
            try:
                pmid = article.findtext(".//PMID", "")
                title = article.findtext(".//ArticleTitle", "")
                abstract_parts = [t.text or "" for t in article.findall(".//AbstractText")]
                abstract = " ".join(abstract_parts)
                year_el = article.find(".//PubDate/Year")
                year = int(year_el.text) if year_el is not None and year_el.text else None
                doi_el = article.find(".//ArticleId[@IdType='doi']")
                doi = doi_el.text if doi_el is not None else None
                journal = article.findtext(".//Journal/Title", "")
                authors = []
                for a in article.findall(".//Author"):
                    ln = a.findtext("LastName", "")
                    fn = a.findtext("ForeName", "")
                    if ln:
                        authors.append(f"{ln} {fn}".strip())
                records.append({
                    "pmid": pmid, "title": title, "abstract": abstract,
                    "year": year, "doi": doi, "journal": journal,
                    "authors": authors, "source": "pubmed"
                })
            except Exception as e:
                continue
        if api_key:
            time.sleep(0.1)
        else:
            time.sleep(0.34)

    return records


# ── OpenAlex ───────────────────────────────────────────────────────────────────

def search_openalex(query: str, max_results: int = 2000, email: str = None) -> list:
    results = []
    cursor = "*"
    params_base = {
        "search": query,
        "per-page": 200,
        "filter": "type:journal-article|review",
    }
    if email:
        params_base["mailto"] = email

    while len(results) < max_results:
        params = {**params_base, "cursor": cursor}
        r = requests.get("https://api.openalex.org/works", params=params, timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        batch = data.get("results", [])
        if not batch:
            break

        for w in batch:
            # Reconstruct abstract from inverted index
            inv = w.get("abstract_inverted_index") or {}
            if inv:
                word_pos = [(word, pos) for word, positions in inv.items() for pos in positions]
                word_pos.sort(key=lambda x: x[1])
                abstract = " ".join(w for w, _ in word_pos)
            else:
                abstract = ""

            results.append({
                "title": w.get("title", ""),
                "abstract": abstract,
                "year": w.get("publication_year"),
                "doi": w.get("doi", "").replace("https://doi.org/", "") if w.get("doi") else None,
                "journal": (w.get("primary_location") or {}).get("source", {}).get("display_name", ""),
                "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
                "citations": w.get("cited_by_count", 0),
                "oa_url": (w.get("open_access") or {}).get("oa_url"),
                "openalex_id": w.get("id"),
                "source": "openalex"
            })

        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.12)  # polite pool

    print(f"  OpenAlex: fetched {len(results)}")
    return results[:max_results]


# ── Semantic Scholar ───────────────────────────────────────────────────────────

def search_semantic_scholar(query: str, max_results: int = 500, api_key: str = None) -> list:
    results = []
    offset = 0
    fields = "paperId,title,abstract,year,authors,externalIds,citationCount,isOpenAccess,openAccessPdf"
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    while len(results) < max_results:
        limit = min(100, max_results - len(results))
        r = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": query, "limit": limit, "offset": offset, "fields": fields},
            headers=headers, timeout=30
        )
        if r.status_code != 200:
            break
        data = r.json()
        batch = data.get("data", [])
        if not batch:
            break
        for p in batch:
            ext = p.get("externalIds") or {}
            results.append({
                "title": p.get("title", ""),
                "abstract": p.get("abstract", ""),
                "year": p.get("year"),
                "doi": ext.get("DOI"),
                "pmid": ext.get("PubMed"),
                "authors": [a["name"] for a in p.get("authors", [])],
                "citations": p.get("citationCount", 0),
                "oa_url": (p.get("openAccessPdf") or {}).get("url"),
                "s2_id": p.get("paperId"),
                "source": "semantic_scholar"
            })
        offset += len(batch)
        if offset >= data.get("total", 0):
            break
        time.sleep(1.1)  # S2 is strict about rate limits

    print(f"  Semantic Scholar: fetched {len(results)}")
    return results


# ── bioRxiv / medRxiv ─────────────────────────────────────────────────────────

def search_biorxiv_via_openalex(query: str, max_results: int = 500, email: str = None) -> list:
    """Search preprints via OpenAlex with bioRxiv/medRxiv source filter."""
    results = []
    params = {
        "search": query,
        "per-page": 100,
        "filter": "primary_location.source.display_name:bioRxiv|primary_location.source.display_name:medRxiv",
    }
    if email:
        params["mailto"] = email

    r = requests.get("https://api.openalex.org/works", params=params, timeout=30)
    if r.status_code == 200:
        for w in r.json().get("results", [])[:max_results]:
            inv = w.get("abstract_inverted_index") or {}
            if inv:
                word_pos = [(word, pos) for word, positions in inv.items() for pos in positions]
                word_pos.sort(key=lambda x: x[1])
                abstract = " ".join(w for w, _ in word_pos)
            else:
                abstract = ""
            results.append({
                "title": w.get("title", ""), "abstract": abstract,
                "year": w.get("publication_year"),
                "doi": w.get("doi", "").replace("https://doi.org/", "") if w.get("doi") else None,
                "authors": [a["author"]["display_name"] for a in w.get("authorships", [])],
                "source": "biorxiv_medrxiv", "preprint": True
            })
    print(f"  bioRxiv/medRxiv: fetched {len(results)}")
    return results


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Multi-database systematic review harvester")
    parser.add_argument("--query", required=True)
    parser.add_argument("--databases", nargs="+",
                        default=["pubmed", "openalex", "semantic_scholar"],
                        choices=["pubmed", "openalex", "semantic_scholar", "biorxiv"])
    parser.add_argument("--max-per-db", type=int, default=2000)
    parser.add_argument("--email", default=None)
    parser.add_argument("--pubmed-api-key", default=None)
    parser.add_argument("--s2-api-key", default=None)
    parser.add_argument("--output", default="results/raw_results.json")
    args = parser.parse_args()

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)

    all_records = []
    search_log = {
        "query": args.query,
        "date": datetime.utcnow().isoformat() + "Z",
        "databases": args.databases,
        "counts": {}
    }

    if "pubmed" in args.databases:
        print("Searching PubMed...")
        records = search_pubmed(args.query, args.max_per_db, args.pubmed_api_key)
        search_log["counts"]["pubmed"] = len(records)
        all_records.extend(records)

    if "openalex" in args.databases:
        print("Searching OpenAlex...")
        records = search_openalex(args.query, args.max_per_db, args.email)
        search_log["counts"]["openalex"] = len(records)
        all_records.extend(records)

    if "semantic_scholar" in args.databases:
        print("Searching Semantic Scholar...")
        records = search_semantic_scholar(args.query, min(args.max_per_db, 1000), args.s2_api_key)
        search_log["counts"]["semantic_scholar"] = len(records)
        all_records.extend(records)

    if "biorxiv" in args.databases:
        print("Searching bioRxiv/medRxiv via OpenAlex...")
        records = search_biorxiv_via_openalex(args.query, 500, args.email)
        search_log["counts"]["biorxiv"] = len(records)
        all_records.extend(records)

    search_log["total_raw"] = len(all_records)
    print(f"\nTotal raw records: {len(all_records)}")

    # Save
    output = {"search_log": search_log, "records": all_records}
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2, default=str)

    # Save search log separately for PRISMA
    log_path = Path(args.output).parent / "search_log.json"
    with open(log_path, "w") as f:
        json.dump(search_log, f, indent=2)

    print(f"Saved to {args.output}")
    print(f"Search log: {log_path}")


if __name__ == "__main__":
    main()
