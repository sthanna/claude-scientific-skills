# Database Reference for Systematic Reviews

## PubMed / MEDLINE

**API**: E-utilities (NCBI)
**Base URL**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
**Rate limit**: 3 req/s (anonymous), 10 req/s (with API key)
**API key**: Free at https://www.ncbi.nlm.nih.gov/account/

### Key endpoints
```
esearch.fcgi  - search → get PMIDs
efetch.fcgi   - fetch records by PMID (XML/JSON)
einfo.fcgi    - database info
```

### Search example
```python
import requests

def pubmed_search(query, max_results=1000, api_key=None):
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
    params = {
        "db": "pubmed", "term": query,
        "retmax": min(max_results, 10000),
        "retmode": "json", "usehistory": "y"
    }
    if api_key:
        params["api_key"] = api_key
    r = requests.get(base + "esearch.fcgi", params=params)
    data = r.json()
    webenv = data["esearchresult"]["webenv"]
    query_key = data["esearchresult"]["querykey"]
    count = int(data["esearchresult"]["count"])
    return webenv, query_key, count
```

### Field tags for advanced queries
```
[MeSH Terms]   – controlled vocabulary
[Title/Abstract]
[Author]
[Journal]
[Publication Type] – e.g., "Clinical Trial[pt]", "Review[pt]"
[Date - Publication] – e.g., "2020:2024[dp]"
[Pharmacological Action] – MeSH drug classification
```

---

## OpenAlex

**API**: REST, no auth required (email for polite pool)
**Base URL**: `https://api.openalex.org`
**Rate limit**: 100k/day; 10 req/s with `?mailto=you@email.com`
**Coverage**: 240M+ works, open access metadata

### Key filters for systematic reviews
```
publication_year: >2019
is_oa: true
type: journal-article | review | clinical-trial
concepts.display_name: "Tuberculosis"
open_access.oa_status: gold | green | hybrid
cited_by_count: >10
```

### Fetch full page example
```python
def openalex_search(query, email, max_results=2000):
    results = []
    cursor = "*"
    while len(results) < max_results:
        r = requests.get(
            "https://api.openalex.org/works",
            params={
                "search": query, "per-page": 200,
                "cursor": cursor, "mailto": email,
                "filter": "type:journal-article"
            }
        )
        data = r.json()
        results.extend(data["results"])
        cursor = data["meta"].get("next_cursor")
        if not cursor:
            break
    return results
```

### Field mapping to standard schema
```python
def openalex_to_standard(work):
    return {
        "title": work.get("title"),
        "abstract": " ".join(work.get("abstract_inverted_index", {}).keys()),  # Note: inverted index
        "authors": [a["author"]["display_name"] for a in work.get("authorships", [])],
        "year": work.get("publication_year"),
        "doi": work.get("doi"),
        "journal": work.get("primary_location", {}).get("source", {}).get("display_name"),
        "citations": work.get("cited_by_count"),
        "open_access_url": work.get("open_access", {}).get("oa_url"),
        "source": "openalex"
    }
```

> ⚠️ OpenAlex abstracts are stored as inverted index — extract with `" ".join(abstract_inverted_index.keys())` for approximate reconstruction, or use `abstract_inverted_index_to_text()` helper.

---

## Semantic Scholar

**API**: REST
**Base URL**: `https://api.semanticscholar.org/graph/v1/`
**Rate limit**: 100 req/min (anonymous), 1 req/s → ~5k/day; API key → higher
**API key**: Free at https://www.semanticscholar.org/product/api
**Best for**: Full text links, citation context, influential citations flag

### Paper search
```python
def semantic_scholar_search(query, fields=None, limit=100):
    if fields is None:
        fields = "paperId,title,abstract,year,authors,externalIds,citationCount,isOpenAccess,openAccessPdf"
    r = requests.get(
        "https://api.semanticscholar.org/graph/v1/paper/search",
        params={"query": query, "limit": min(limit, 100), "fields": fields},
        headers={"x-api-key": "YOUR_KEY"}  # optional
    )
    return r.json()["data"]
```

### Bulk fetch by DOI list
```python
def bulk_fetch_s2(doi_list):
    r = requests.post(
        "https://api.semanticscholar.org/graph/v1/paper/batch",
        params={"fields": "paperId,title,abstract,citationCount"},
        json={"ids": [f"DOI:{d}" for d in doi_list]}
    )
    return r.json()
```

---

## bioRxiv / medRxiv

**API**: REST
**Base URL**: `https://api.biorxiv.org/`
**Rate limit**: Generous, no auth required

### Search by date range + category
```python
def biorxiv_search(start_date, end_date, server="biorxiv", cursor=0):
    # Returns papers in date range
    r = requests.get(
        f"https://api.biorxiv.org/details/{server}/{start_date}/{end_date}/{cursor}"
    )
    return r.json()
```

Categories: biochemistry, biophysics, cancer-biology, clinical-trials-epidemiology, microbiology, pharmacology-toxicology, etc.

> Note: bioRxiv doesn't support free-text search via API. Use the Semantic Scholar API with `venue:bioRxiv` filter, or OpenAlex with `host_venue.display_name:bioRxiv`.

---

## Deduplication Logic

Priority for keeping canonical record:
1. PubMed record (most complete metadata)
2. Semantic Scholar (has full-text links)
3. OpenAlex (has citation counts)
4. bioRxiv (preprint — mark as preprint)

Matching strategy (any match = duplicate):
1. Exact DOI match
2. Exact PMID match
3. Fuzzy title match: `rapidfuzz.fuzz.token_sort_ratio(t1, t2) > 92`
4. Same year + same first author surname + title similarity > 85

```python
from rapidfuzz import fuzz

def is_duplicate(r1, r2):
    if r1.get("doi") and r1["doi"] == r2.get("doi"):
        return True
    if r1.get("pmid") and r1["pmid"] == r2.get("pmid"):
        return True
    if r1.get("year") == r2.get("year"):
        if fuzz.token_sort_ratio(r1["title"], r2["title"]) > 92:
            return True
    return False
```

Install: `uv pip install rapidfuzz`
