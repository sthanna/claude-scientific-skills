# OpenAlex Field Reference

## API Base

`https://api.openalex.org`
No auth required. Add `?mailto=your@email.com` for 10x rate limit (polite pool).

## Works Endpoint Fields

Key fields available via `?select=`:

```
id                          — OpenAlex ID
doi                         — DOI string
title
publication_year
publication_date
type                        — journal-article | review | book-chapter | preprint | ...
cited_by_count
abstract_inverted_index     — dict {word: [positions]} — reconstruct text by sorting positions
authorships                 — list of {author: {id, display_name}, institutions: [...]}
primary_location            — {source: {display_name, issn_l, is_oa}, is_oa, landing_page_url}
open_access                 — {is_oa, oa_status, oa_url}
concepts                    — [{display_name, score, level}] — OpenAlex taxonomy
keywords                    — [{display_name, score}]
topics                      — [{display_name, domain, field, subfield}]
referenced_works            — list of OpenAlex IDs (references)
related_works               — list of OpenAlex IDs
grants                      — [{funder: {display_name}, award_id}]
```

## Filter Syntax

Combine filters with commas (AND logic):
```
filter=publication_year:2020-2024,type:journal-article,is_oa:true
```

### Year filters
```
publication_year:2024           — exact year
publication_year:2020-2024      — range
publication_year:>2019          — greater than
```

### Type filters
```
type:journal-article
type:review
type:book-chapter
type:preprint
type:clinical-trial
```

### Open access
```
is_oa:true
open_access.oa_status:gold       — gold OA
open_access.oa_status:green      — green OA (repository copy)
open_access.oa_status:bronze     — publisher free-to-read
```

### Concept/topic filters (use for field scoping)
```
concepts.display_name:Tuberculosis
topics.display_name:"Vaccine Development"
topics.field.display_name:"Immunology"
topics.domain.display_name:"Health Sciences"
```

### Citation threshold
```
cited_by_count:>50              — more than 50 citations
cited_by_count:>100
```

### Institution / country
```
authorships.institutions.country_code:US
authorships.institutions.display_name:"Pfizer"
authorships.institutions.ror:https://ror.org/01cwqze88
```

### Author
```
authorships.author.id:A1234567890    — by OpenAlex author ID
```

## Sort Options

```
sort=cited_by_count:desc      — most cited first
sort=publication_date:desc    — newest first
sort=relevance_score:desc     — best text match (only with search=)
```

## Pagination

Use cursor-based pagination for large result sets:
```
per-page=200        — max 200 per request
cursor=*            — initial cursor
cursor=<next>       — from meta.next_cursor in response
```

Never use page= parameter for bulk extraction (unreliable beyond page 10k).

## Authors Endpoint

`GET /authors?search=Jennifer+Doudna&mailto=...`

Key fields: `id`, `display_name`, `works_count`, `cited_by_count`, `summary_stats.h_index`, `affiliations`

## Concepts Endpoint

Browse OpenAlex concept taxonomy:
`GET /concepts?search=tuberculosis`

Levels 0–5 (0=broadest: Medicine, Chemistry, Biology; 5=narrowest).

## Sample Queries

### Top cited papers in a field (2020+)
```
/works?search=bedaquiline+tuberculosis&filter=publication_year:>2019,type:journal-article&sort=cited_by_count:desc&per-page=50
```

### All papers from Pfizer (by ROR)
```
/works?filter=authorships.institutions.ror:https://ror.org/01cwqze88&sort=publication_year:desc
```

### Author h-index lookup
```
/authors?search=Sandeep+Thanna
→ use returned ID to get works: /works?filter=authorships.author.id:A{id}
```

### Open access papers in journals (by ISSN)
```
/works?filter=primary_location.source.issn:0022-2623,is_oa:true
```
