#!/usr/bin/env python3
"""
Bibliometric field analysis using OpenAlex.

Usage:
    python scripts/analyze.py \
      --topic "glycoconjugate vaccine" \
      --years 2010 2024 \
      --email your@email.com \
      --top-n 20 \
      --output results/
      
    python scripts/analyze.py --topic "CRISPR" --mode authors --top-n 30
    python scripts/analyze.py --topic "mRNA vaccine" --mode papers --top-n 50
    python scripts/analyze.py --topic "antibody drug conjugate" --mode journals

Requires: uv pip install requests pandas matplotlib
"""

import json
import argparse
import time
import requests
import csv
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime


# ── OpenAlex fetch ─────────────────────────────────────────────────────────────

def fetch_papers(topic: str, year_start: int, year_end: int,
                 email: str = None, max_results: int = 5000) -> list:
    """Fetch papers for a topic from OpenAlex."""
    results = []
    cursor = "*"
    params_base = {
        "search": topic,
        "per-page": 200,
        "filter": f"publication_year:{year_start}-{year_end},type:journal-article|review",
        "select": "id,doi,title,publication_year,cited_by_count,authorships,primary_location,"
                  "keywords,concepts,abstract_inverted_index,open_access",
    }
    if email:
        params_base["mailto"] = email

    while len(results) < max_results:
        r = requests.get("https://api.openalex.org/works",
                         params={**params_base, "cursor": cursor}, timeout=30)
        if r.status_code != 200:
            print(f"  OpenAlex error {r.status_code}")
            break
        data = r.json()
        batch = data.get("results", [])
        if not batch:
            break
        results.extend(batch)
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        time.sleep(0.12)

    print(f"Fetched {len(results)} papers for '{topic}' ({year_start}-{year_end})")
    return results[:max_results]


def openalex_abstract(work: dict) -> str:
    inv = work.get("abstract_inverted_index") or {}
    if not inv:
        return ""
    word_pos = [(w, p) for w, positions in inv.items() for p in positions]
    word_pos.sort(key=lambda x: x[1])
    return " ".join(w for w, _ in word_pos)


# ── Author metrics ─────────────────────────────────────────────────────────────

def compute_author_metrics(papers: list) -> list:
    """Compute per-author bibliometric metrics."""
    author_papers = defaultdict(list)  # author_id → list of (citations, year, title)
    author_names = {}
    author_institutions = {}

    for p in papers:
        for auth in p.get("authorships", []):
            a = auth.get("author", {})
            aid = a.get("id", "")
            if not aid:
                continue
            author_names[aid] = a.get("display_name", "Unknown")
            insts = auth.get("institutions", [])
            if insts:
                author_institutions[aid] = insts[0].get("display_name", "")
            author_papers[aid].append({
                "citations": p.get("cited_by_count", 0),
                "year": p.get("publication_year"),
                "title": p.get("title", ""),
                "doi": p.get("doi", ""),
            })

    rows = []
    for aid, plist in author_papers.items():
        citation_counts = sorted([p["citations"] for p in plist], reverse=True)
        h = sum(1 for i, c in enumerate(citation_counts) if c >= i + 1)
        total_cites = sum(citation_counts)
        years = [p["year"] for p in plist if p["year"]]
        career_years = (max(years) - min(years) + 1) if len(years) > 1 else 1
        m_index = round(h / career_years, 2) if career_years else 0
        rows.append({
            "author_id": aid,
            "name": author_names.get(aid, "Unknown"),
            "institution": author_institutions.get(aid, ""),
            "papers_in_field": len(plist),
            "total_citations": total_cites,
            "h_index": h,
            "m_index": m_index,
            "i10_index": sum(1 for c in citation_counts if c >= 10),
            "avg_citations": round(total_cites / len(plist), 1) if plist else 0,
            "active_years": f"{min(years, default='?')}-{max(years, default='?')}",
        })

    return sorted(rows, key=lambda x: x["h_index"], reverse=True)


# ── Paper metrics ──────────────────────────────────────────────────────────────

def top_papers(papers: list, n: int = 50) -> list:
    """Rank papers by citations, annotate with burst/founder status."""
    enriched = []
    current_year = datetime.now().year
    field_avg = sum(p.get("cited_by_count", 0) for p in papers) / max(len(papers), 1)

    for p in papers:
        year = p.get("publication_year") or current_year
        age = current_year - year + 1
        cites = p.get("cited_by_count", 0)
        rate = cites / age

        tags = []
        if cites > 5 * field_avg:
            tags.append("highly_cited")
        if age >= 5 and cites > 100 and rate > field_avg * 2:
            tags.append("field_founder")
        if rate > field_avg * 3:
            tags.append("citation_burst")

        authors = p.get("authorships", [])
        author_str = ", ".join(
            a["author"]["display_name"] for a in authors[:3] if a.get("author")
        )
        if len(authors) > 3:
            author_str += " et al."

        enriched.append({
            "title": p.get("title", ""),
            "year": year,
            "citations": cites,
            "citation_rate_per_year": round(rate, 1),
            "journal": (p.get("primary_location") or {}).get("source", {}).get("display_name", ""),
            "doi": p.get("doi", "").replace("https://doi.org/", "") if p.get("doi") else "",
            "authors": author_str,
            "tags": tags,
        })

    return sorted(enriched, key=lambda x: x["citations"], reverse=True)[:n]


# ── Journal metrics ────────────────────────────────────────────────────────────

def journal_metrics(papers: list) -> list:
    journals = defaultdict(lambda: {"papers": 0, "total_citations": 0, "names": []})
    for p in papers:
        loc = (p.get("primary_location") or {}).get("source", {})
        name = loc.get("display_name", "Unknown")
        cites = p.get("cited_by_count", 0)
        journals[name]["papers"] += 1
        journals[name]["total_citations"] += cites

    rows = []
    for name, data in journals.items():
        if name == "Unknown":
            continue
        citation_counts = sorted(
            [p.get("cited_by_count", 0) for p in papers
             if (p.get("primary_location") or {}).get("source", {}).get("display_name") == name],
            reverse=True
        )
        h = sum(1 for i, c in enumerate(citation_counts) if c >= i + 1)
        rows.append({
            "journal": name,
            "papers_in_field": data["papers"],
            "total_citations": data["total_citations"],
            "avg_citations": round(data["total_citations"] / data["papers"], 1),
            "h_index_in_field": h,
        })

    return sorted(rows, key=lambda x: x["total_citations"], reverse=True)


# ── Keyword trends ─────────────────────────────────────────────────────────────

def keyword_trends(papers: list) -> dict:
    """Track keyword frequency by year."""
    trends = defaultdict(lambda: defaultdict(int))
    for p in papers:
        year = p.get("publication_year")
        if not year:
            continue
        for kw in p.get("keywords", []):
            keyword = kw.get("display_name", "").lower()
            if keyword:
                trends[keyword][year] += 1
        for concept in p.get("concepts", [])[:5]:
            concept_name = concept.get("display_name", "").lower()
            score = concept.get("score", 0)
            if concept_name and score > 0.3:
                trends[concept_name][year] += 1

    # Top keywords by total count
    total_counts = {kw: sum(years.values()) for kw, years in trends.items()}
    top_keywords = sorted(total_counts.items(), key=lambda x: x[1], reverse=True)[:30]
    return {kw: dict(trends[kw]) for kw, _ in top_keywords}


# ── Report generation ──────────────────────────────────────────────────────────

def save_csv(rows: list, path: str):
    if not rows:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved {path}")


def generate_report(topic, papers, authors, top_paps, journals, kw_trends, output_dir):
    """Generate markdown summary report."""
    from datetime import datetime

    n_papers = len(papers)
    total_cites = sum(p.get("cited_by_count", 0) for p in papers)
    years = [p.get("publication_year") for p in papers if p.get("publication_year")]
    year_range = f"{min(years)}-{max(years)}" if years else "?"

    # Year distribution
    year_counts = Counter(years)

    report = f"""# Bibliometric Analysis: {topic}
*Generated: {datetime.utcnow().strftime('%Y-%m-%d')} | Data: OpenAlex*

## Field Overview

| Metric | Value |
|---|---|
| Papers analyzed | {n_papers:,} |
| Total citations | {total_cites:,} |
| Period | {year_range} |
| Avg citations/paper | {total_cites/n_papers:.1f} |
| Top year | {max(year_counts, key=year_counts.get) if year_counts else '?'} ({max(year_counts.values()) if year_counts else '?'} papers) |

## Top 10 Authors by h-index

| Rank | Author | Institution | Papers | h-index | Total Citations |
|---|---|---|---|---|---|
"""
    for i, a in enumerate(authors[:10], 1):
        report += f"| {i} | {a['name']} | {a['institution'][:40] if a['institution'] else 'N/A'} | {a['papers_in_field']} | {a['h_index']} | {a['total_citations']:,} |\n"

    report += "\n## Top 10 Most-Cited Papers\n\n"
    for i, p in enumerate(top_paps[:10], 1):
        tags_str = " 🔥" if "citation_burst" in p["tags"] else ""
        tags_str += " 🏛️" if "field_founder" in p["tags"] else ""
        report += f"**{i}.** {p['title']}{tags_str}  \n"
        report += f"*{p['authors']}* | {p['journal']} | {p['year']} | **{p['citations']} citations**\n\n"

    report += "\n## Top 10 Journals\n\n"
    report += "| Journal | Papers | Total Citations | Avg Citations |\n|---|---|---|---|\n"
    for j in journals[:10]:
        report += f"| {j['journal']} | {j['papers_in_field']} | {j['total_citations']:,} | {j['avg_citations']} |\n"

    report += "\n## Emerging Keywords (last 5 years)\n\n"
    current_year = datetime.now().year
    recent_kws = {}
    for kw, yr_counts in kw_trends.items():
        recent = sum(v for y, v in yr_counts.items() if y and y >= current_year - 5)
        if recent > 0:
            recent_kws[kw] = recent
    top_recent = sorted(recent_kws.items(), key=lambda x: x[1], reverse=True)[:15]
    report += ", ".join(f"`{kw}` ({n})" for kw, n in top_recent)
    report += "\n"

    out_path = Path(output_dir) / "report.md"
    with open(out_path, "w") as f:
        f.write(report)
    print(f"  Report saved: {out_path}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Bibliometric field analysis")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--years", nargs=2, type=int, default=[2015, 2024])
    parser.add_argument("--email", default=None)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--mode", default="all",
                        choices=["all", "authors", "papers", "journals", "keywords"])
    parser.add_argument("--max-papers", type=int, default=5000)
    parser.add_argument("--output", default="results/")
    args = parser.parse_args()

    Path(args.output).mkdir(parents=True, exist_ok=True)

    # Fetch
    papers = fetch_papers(args.topic, args.years[0], args.years[1],
                          args.email, args.max_papers)

    # Save raw
    papers_path = Path(args.output) / "papers.json"
    with open(papers_path, "w") as f:
        json.dump(papers, f, indent=2, default=str)
    print(f"  Papers saved: {papers_path}")

    if args.mode in ("all", "authors"):
        print("Computing author metrics...")
        authors = compute_author_metrics(papers)[:args.top_n]
        save_csv(authors, str(Path(args.output) / f"authors_top{args.top_n}.csv"))

    if args.mode in ("all", "papers"):
        print("Ranking papers...")
        top_paps = top_papers(papers, args.top_n)
        save_csv(top_paps, str(Path(args.output) / f"papers_top{args.top_n}.csv"))

    if args.mode in ("all", "journals"):
        print("Computing journal metrics...")
        journals = journal_metrics(papers)
        save_csv(journals, str(Path(args.output) / "journals_ranking.csv"))

    if args.mode in ("all", "keywords"):
        print("Extracting keyword trends...")
        kw = keyword_trends(papers)
        kw_path = Path(args.output) / "keyword_trends.json"
        with open(kw_path, "w") as f:
            json.dump(kw, f, indent=2)
        print(f"  Keywords saved: {kw_path}")

    if args.mode == "all":
        print("Generating report...")
        generate_report(
            args.topic, papers,
            compute_author_metrics(papers),
            top_papers(papers, 20),
            journal_metrics(papers),
            keyword_trends(papers),
            args.output
        )

    print(f"\nDone. Results in {args.output}")


if __name__ == "__main__":
    main()
