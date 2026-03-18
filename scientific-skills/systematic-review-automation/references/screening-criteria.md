# Screening Criteria Reference

## PICO Template

```yaml
population: ""          # Who? (disease, condition, demographics)
intervention: ""        # What treatment/exposure/test?
comparison: ""          # Compared to what? (placebo, standard care, none)
outcome: ""             # What was measured? (primary + secondary)
study_types:            # Which study designs are eligible?
  - RCT
  - cohort
  - case-control
  - systematic_review
date_range: [2015, 2024]
languages: [English]    # add others if translated
```

## SPIDER Template (qualitative/mixed)

```yaml
sample: ""              # Who? (people, populations)
phenomenon_of_interest: ""
design: ""              # Study design (qualitative, survey, mixed)
evaluation: ""          # Outcomes/themes being studied
research_type: qualitative | quantitative | mixed
```

## Standard Inclusion Criteria

```python
INCLUSION = {
    "study_types": ["RCT", "cohort", "case-control", "cross-sectional", "meta-analysis"],
    "min_sample_size": 10,          # Adjust per domain
    "human_subjects": True,
    "language": ["English"],        # Extend as needed
    "full_text_available": False,   # Don't exclude if not OA by default
}

EXCLUSION = {
    "study_types": ["editorial", "letter", "comment", "conference_abstract"],
    "animal_only": True,
    "in_vitro_only": True,         # Adjust: sometimes in vitro is relevant
    "duplicate": True,
    "protocol_only": True,          # Registered trial with no results
}
```

## Pharmaceutical / Vaccine Domain Criteria

Additional filters common in drug discovery and vaccine development reviews:

```python
PHARMA_INCLUSION = {
    "phases": ["Phase I", "Phase II", "Phase III", "Phase IV"],
    "endpoints": ["efficacy", "safety", "immunogenicity", "seroconversion",
                  "AUC", "Cmax", "IC50", "EC50", "binding affinity"],
    "population_keywords": ["patient", "volunteer", "subject", "participant",
                            "healthy adult", "pediatric"],
}

PHARMA_EXCLUSION = {
    "exclude_if_no_control": False,     # Set True for efficacy reviews
    "exclude_case_reports": True,
    "exclude_if_no_dose_data": False,
}
```

## Relevance Scoring

Simple keyword-based scoring for title/abstract screen. Scores 0.0–1.0.

```python
def score_record(title: str, abstract: str, pico: dict) -> dict:
    text = (title + " " + abstract).lower()
    
    # Positive signals
    population_hit = any(kw in text for kw in pico["population_keywords"])
    intervention_hit = any(kw in text for kw in pico["intervention_keywords"])
    outcome_hit = any(kw in text for kw in pico["outcome_keywords"])
    study_type_hit = any(kw in text for kw in pico["study_type_keywords"])
    
    # Negative signals
    exclusion_hit = any(kw in text for kw in pico.get("exclusion_keywords", []))
    
    # Weighted score
    score = (
        0.30 * population_hit +
        0.30 * intervention_hit +
        0.25 * outcome_hit +
        0.15 * study_type_hit -
        0.50 * exclusion_hit
    )
    score = max(0.0, min(1.0, score))
    
    if score >= 0.7:
        decision = "include"
    elif score <= 0.2 or exclusion_hit:
        decision = "exclude"
    else:
        decision = "uncertain"
    
    return {
        "score": round(score, 3),
        "decision": decision,
        "confidence": score if decision != "uncertain" else 0.5,
        "flags": {
            "population": population_hit,
            "intervention": intervention_hit,
            "outcome": outcome_hit,
            "study_type": study_type_hit,
            "exclusion_trigger": exclusion_hit,
        }
    }
```

## GRADE Evidence Quality Assessment

For each outcome across included studies, assess:

| Domain | Questions |
|---|---|
| Risk of bias | Were included studies at low/high risk? (RoB 2, ROBINS-I) |
| Inconsistency | Large variability in results (I² > 60%)? |
| Indirectness | Different population/intervention/outcome from review question? |
| Imprecision | Wide CI, small total sample (n < 400 for continuous)? |
| Publication bias | Asymmetric funnel plot? |

**GRADE levels**: High → Moderate → Low → Very Low
- Start at High for RCTs, Low for observational
- Downgrade 1 level per domain with serious concerns
- Upgrade if large effect, dose-response, or all plausible confounders favour intervention

## Inter-rater Agreement

For dual screening, calculate Cohen's kappa after independent review:

```python
from sklearn.metrics import cohen_kappa_score

kappa = cohen_kappa_score(reviewer_1_decisions, reviewer_2_decisions)
# Target: kappa > 0.8 (almost perfect)
# Acceptable: kappa > 0.6 (substantial)
# Below 0.6: revisit criteria and retrain
```

Conflicts (where reviewers disagree): resolve by discussion, or third reviewer.
