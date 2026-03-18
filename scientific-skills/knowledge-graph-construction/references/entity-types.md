# Entity Types Reference

## Full Entity Taxonomy

### Drug / Compound
**Examples**: bedaquiline, ebselen, TMC207, linezolid, AMB-101, bevacizumab  
**Sub-types**: small molecule, biologic/mAb, prodrug, natural product, fragment  
**Key identifiers**: ChEBI ID, DrugBank ID, PubChem CID, InChI, SMILES  
**Extraction signals**: compound names, CAS numbers, INN names, trade names, `-mab`/`-nib`/`-lib` suffixes  

```python
# Pattern examples
DRUG_SIGNALS = [
    r'\b[A-Z]{2,4}-\d{3,}\b',           # GSK2981278, AMB-101
    r'\b\w+(?:mab|nib|lib|zumab|ximab|umab)\b',  # biologics
    r'\bIC50\s*[=<>≤≥]\s*[\d.]+\s*[nμm]M\b',    # with activity data
    r'\bcompound \d+[a-z]?\b',           # compound 5a, compound 12
]
```

### Gene / Protein
**Examples**: GlgE, InhA, EGFR, TP53, TNF-α, GlpK, KasB  
**Sub-types**: enzyme, transcription factor, receptor, kinase, transporter, structural protein  
**Key identifiers**: UniProt accession, HGNC symbol, Entrez Gene ID, PDB code  
**Extraction signals**: gene symbols (all-caps 2–6 chars), protein names with organism context  

```python
GENE_SIGNALS = [
    r'\b[A-Z][a-z]{0,2}[A-Z]\w{1,6}\b',   # CamelCase: GlgE, MmpL3
    r'\b[A-Z]{2,5}\d*[A-Z]?\b',            # EGFR, BRAF, TP53
    r'\bp\d{2,3}\b',                         # p53, p21, p65
    r'\bEC\s*\d+\.\d+\.\d+\.\d+\b',        # enzyme commission numbers
]
```

### Disease / Condition
**Examples**: tuberculosis, MDR-TB, Alzheimer's disease, non-small cell lung cancer  
**Sub-types**: infectious disease, cancer, neurological, metabolic, rare disease  
**Key identifiers**: MeSH term, OMIM ID, DO (Disease Ontology), ICD-10  
**Extraction signals**: disease names, synonyms, stage/grade qualifiers  

### Pathway
**Examples**: trehalose utilization pathway, mTOR signaling, oxidative phosphorylation  
**Sub-types**: metabolic, signaling, transcriptional, cell death  
**Key identifiers**: KEGG pathway ID (hsa04xxx), Reactome ID (R-HSA-xxx)  
**Extraction signals**: "__ pathway", "__ signaling", "__ cascade"  

### Mechanism / Activity
**Examples**: competitive inhibition, covalent binding, allosteric activation  
**Relation to relations**: mechanisms often ARE the relation type between Drug and Target  
**Key qualifiers**: reversible/irreversible, covalent/non-covalent, Ki/IC50/Kd values  

### Organism / Taxon
**Examples**: Mycobacterium tuberculosis H37Rv, MRSA, C57BL/6 mouse  
**Key identifiers**: NCBI Taxonomy ID, strain designation  
**Extraction signals**: binomial names, strain IDs, serogroups  

### Assay / Method
**Examples**: SPR, MALDI-TOF, IC50 assay, MIC determination, Western blot  
**Why extract**: Links experimental evidence to claims; enables method-specific filtering  
**Key identifiers**: BAO (BioAssay Ontology), OBI (Ontology for Biomedical Investigations)  

### Modification / Post-translational
**Examples**: N-glycosylation, phosphorylation at Ser473, ubiquitination  
**Key identifiers**: MOD ontology, UniMod  
**Extraction signals**: amino acid position + modification type  

### Cell Type / Tissue
**Examples**: alveolar macrophage, CD4+ T cell, hepatocyte, bone marrow  
**Key identifiers**: Cell Ontology (CL), Uberon (tissue anatomy)  

---

## Pharma-Specific Entity Patterns

### Activity Data (often attached to Drug entities)
Extract quantitative values alongside entity mentions:
```python
ACTIVITY_PATTERNS = [
    r'IC50\s*[=<>≤≥]\s*([\d.]+)\s*(nM|μM|mM)',
    r'Ki\s*[=<>≤≥]\s*([\d.]+)\s*(nM|μM)',
    r'MIC(?:90)?\s*[=<>≤≥]\s*([\d.]+)\s*(μg/mL|mg/L)',
    r'EC50\s*[=<>≤≥]\s*([\d.]+)\s*(nM|μM)',
    r'Kd\s*[=<>≤≥]\s*([\d.]+)\s*(nM|μM|pM)',
]
```

Store as node attributes: `{"entity": "bedaquiline", "type": "Drug", "IC50": "0.06 nM", "target": "AtpE"}`

### Patent / IP Entities
For freedom-to-operate and prior art analysis:
- Patent number (WO/US/EP + number)
- Assignee (company/institution)
- Priority date

```python
PATENT_PATTERN = r'\b(?:WO|US|EP|JP)\s*\d{4}/?\d{6,7}(?:A1|A2|B1|B2)?\b'
```

### Regulatory / Clinical Stage
```python
PHASE_PATTERN = r'\bPhase\s*(?:I{1,3}|IV|1|2|3|4)(?:a|b)?\b'
IND_PATTERN = r'\bIND\b|\bNDA\b|\bBLA\b|\bEMA\b'
```

---

## Relation Types Between Entities

| Source Type | Relation | Target Type | Example |
|---|---|---|---|
| Drug | INHIBITS | Gene/Protein | bedaquiline INHIBITS AtpE |
| Drug | BINDS | Gene/Protein | ebselen BINDS Mpro |
| Drug | TREATS | Disease | bedaquiline TREATS MDR-TB |
| Drug | CAUSES | Disease | drug X CAUSES hepatotoxicity |
| Gene | ASSOCIATED_WITH | Disease | GlgE ASSOCIATED_WITH tuberculosis |
| Gene | PART_OF | Pathway | GlgE PART_OF trehalose utilization |
| Pathway | IMPLICATED_IN | Disease | trehalose utilization IMPLICATED_IN TB |
| Gene | UPREGULATES | Gene | TNF-α UPREGULATES IL-6 |
| Drug | MEASURED_BY | Assay | IC50 MEASURED_BY SPR assay |
| Organism | EXPRESSES | Gene | M. tuberculosis EXPRESSES GlgE |

---

## Normalization Strategy

Always normalize entity text to a canonical form before building graph nodes:

```python
def normalize_entity(text: str, entity_type: str) -> str:
    """Normalize entity name for consistent graph node IDs."""
    text = text.strip().lower()
    
    # Drug normalization
    if entity_type == "Drug":
        text = text.replace("–", "-").replace("—", "-")
        # Remove salt forms: "bedaquiline fumarate" → "bedaquiline"
        text = re.sub(r'\s+(hydrochloride|fumarate|sulfate|sodium|potassium)$', '', text)
    
    # Gene normalization  
    elif entity_type == "Gene/Protein":
        # Standardize Greek letters
        text = text.replace("α", "alpha").replace("β", "beta").replace("γ", "gamma")
        text = text.replace("κ", "kappa")
    
    # Disease normalization
    elif entity_type == "Disease":
        # Expand common abbreviations
        abbrevs = {"TB": "tuberculosis", "MDR-TB": "multidrug-resistant tuberculosis",
                   "AD": "alzheimer's disease", "T2D": "type 2 diabetes"}
        if text.upper() in abbrevs:
            text = abbrevs[text.upper()]
    
    return text
```
