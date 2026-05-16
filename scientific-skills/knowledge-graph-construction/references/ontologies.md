# Biomedical Ontologies Reference

## Why Normalize to Ontology IDs?

Raw text extraction gives "tuberculosis", "TB", "Mtb disease", "pulmonary TB" — all the same concept. Mapping to a standard ID (MESH:D014376) lets you merge these automatically and query across databases.

---

## Core Ontologies by Entity Type

### Drugs / Compounds → ChEBI + DrugBank

**ChEBI** (Chemical Entities of Biological Interest)
- URL: `https://www.ebi.ac.uk/chebi/`
- API: `https://www.ebi.ac.uk/webservices/chebi/2.0/test/getCompleteEntity?chebiId=CHEBI:123456`
- ID format: `CHEBI:123456`

```python
def lookup_chebi(compound_name: str) -> dict:
    import requests
    r = requests.get(
        "https://www.ebi.ac.uk/chebi/ws/rest/search",
        params={"search": compound_name, "searchCategory": "ALL", "maximumResults": 5}
    )
    if r.status_code == 200:
        results = r.json().get("SearchResult", {}).get("ListElement", [])
        if results:
            top = results[0] if isinstance(results, list) else results
            return {"id": top.get("chebiId"), "name": top.get("chebiName")}
    return {}
```

**DrugBank** — requires account, but free for academic use
- URL: `https://go.drugbank.com/`
- ID format: `DB00xxx`

**PubChem** — free, no auth
```python
def lookup_pubchem(name: str) -> dict:
    import requests
    r = requests.get(
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}/JSON"
    )
    if r.status_code == 200:
        cid = r.json()["PC_Compounds"][0]["id"]["id"]["cid"]
        return {"id": f"CID:{cid}", "name": name}
    return {}
```

---

### Diseases → MeSH + Disease Ontology (DO)

**MeSH** (Medical Subject Headings)
- URL: `https://meshb.nlm.nih.gov/`
- API: `https://id.nlm.nih.gov/mesh/lookup/descriptor?label=tuberculosis`
- ID format: `MESH:D014376`

```python
def lookup_mesh(disease_name: str) -> dict:
    import requests
    r = requests.get(
        "https://id.nlm.nih.gov/mesh/lookup/descriptor",
        params={"label": disease_name, "match": "contains", "limit": 5}
    )
    if r.status_code == 200:
        results = r.json()
        if results:
            top = results[0]
            return {"id": top.get("resource", "").split("/")[-1], "name": top.get("label")}
    return {}
```

**Disease Ontology** — OBO format
- ID format: `DOID:1234`
- API: `https://www.disease-ontology.org/api/search/?term=tuberculosis`

**OMIM** — genetic disease focus, requires free registration
- ID format: `OMIM:278700`

---

### Genes / Proteins → UniProt + HGNC + Entrez

**UniProt** — proteins, free API
```python
def lookup_uniprot(protein_name: str, organism_id: int = 9606) -> dict:
    import requests
    r = requests.get(
        "https://rest.uniprot.org/uniprotkb/search",
        params={"query": f"{protein_name} AND organism_id:{organism_id}",
                "format": "json", "size": 1}
    )
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            top = results[0]
            return {
                "id": top["primaryAccession"],
                "name": top.get("uniProtkbId"),
                "gene": top.get("genes", [{}])[0].get("geneName", {}).get("value")
            }
    return {}
```

**HGNC** — human gene nomenclature
- API: `https://rest.genenames.org/search/symbol/EGFR`
- ID format: `HGNC:3236`

**Entrez Gene** — NCBI genes across all organisms
- ID format: `Gene:1956` (EGFR)
- Access via BioPython or NCBI E-utilities

---

### Pathways → KEGG + Reactome

**KEGG**
```python
def lookup_kegg_pathway(pathway_name: str) -> dict:
    import requests
    r = requests.get(f"https://rest.kegg.jp/find/pathway/{pathway_name.replace(' ', '+')}")
    if r.status_code == 200:
        lines = r.text.strip().split('\n')
        if lines and lines[0]:
            parts = lines[0].split('\t')
            return {"id": parts[0], "name": parts[1] if len(parts) > 1 else pathway_name}
    return {}
```

**Reactome**
- API: `https://reactome.org/ContentService/search/query?query=trehalose+utilization`
- ID format: `R-HSA-xxx` (human), `R-MTU-xxx` (M. tuberculosis)

---

### Gene Ontology (GO)

For molecular function, biological process, cellular component:
- ID format: `GO:0003824` (catalytic activity)
- API: `https://www.ebi.ac.uk/QuickGO/services/ontology/go/terms/{goId}`

Categories:
- `molecular_function` — what the protein does (e.g., ATP binding, enzyme activity)
- `biological_process` — broader biological role (e.g., DNA repair, immune response)  
- `cellular_component` — where it acts (e.g., nucleus, membrane)

---

## Normalization Lookup Order

For each extracted entity, try lookups in this priority:

| Entity Type | 1st choice | 2nd choice | 3rd choice |
|---|---|---|---|
| Drug | ChEBI | PubChem | DrugBank |
| Disease | MeSH | Disease Ontology | OMIM |
| Gene/Protein | UniProt | HGNC | Entrez Gene |
| Pathway | KEGG | Reactome | GO (biological_process) |
| Organism | NCBI Taxonomy | — | — |

If no ontology match found: keep raw text, flag as `normalized: false`.

---

## NCBI Taxonomy (Organisms)

```python
def lookup_taxon(organism_name: str) -> dict:
    import requests
    r = requests.get(
        "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
        params={"db": "taxonomy", "term": organism_name, "retmode": "json"}
    )
    if r.status_code == 200:
        ids = r.json()["esearchresult"]["idlist"]
        if ids:
            return {"id": f"TAXON:{ids[0]}", "name": organism_name}
    return {}
```

Key IDs: Homo sapiens = 9606, M. tuberculosis H37Rv = 83332, E. coli K-12 = 83333

---

## RDF Export Namespaces

When exporting to RDF/Turtle:
```turtle
@prefix chebi: <http://purl.obolibrary.org/obo/CHEBI_> .
@prefix mesh:  <http://id.nlm.nih.gov/mesh/> .
@prefix doid:  <http://purl.obolibrary.org/obo/DOID_> .
@prefix up:    <https://www.uniprot.org/uniprot/> .
@prefix kegg:  <https://www.kegg.jp/entry/> .
@prefix go:    <http://purl.obolibrary.org/obo/GO_> .
@prefix sio:   <http://semanticscience.org/resource/SIO_> .
```
