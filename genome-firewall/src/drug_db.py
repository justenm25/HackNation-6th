"""
Drug knowledge base for Genome Firewall.

For each supported antibiotic:
  - `target`   : the molecular target (for the deterministic target gate)
  - `classes`  : AMRFinderPlus `Class` values that confer resistance to this drug
  - `subclasses`: AMRFinderPlus `Subclass` values that confer resistance to this drug

Used for (a) the target gate — never say "works" purely from absent markers — and
(b) honest evidence: a present gene is a KNOWN cause for a drug only if its
class/subclass matches this table; otherwise it is at most a statistical association.
"""
from __future__ import annotations

DRUGS = {
    "Meropenem": {
        "drug_class": "Carbapenem",
        "target": "penicillin-binding proteins",
        "classes": {"BETA-LACTAM"},
        "subclasses": {"CARBAPENEM"},
    },
    "Ceftazidime": {
        "drug_class": "Cephalosporin",
        "target": "penicillin-binding proteins",
        "classes": {"BETA-LACTAM"},
        "subclasses": {"CEPHALOSPORIN", "CARBAPENEM"},
    },
    "Ciprofloxacin": {
        "drug_class": "Fluoroquinolone",
        "target": "DNA gyrase / topoisomerase IV",
        "classes": {"QUINOLONE"},
        "subclasses": {"FLUOROQUINOLONE", "QUINOLONE"},
    },
    "Gentamicin": {
        "drug_class": "Aminoglycoside",
        "target": "30S ribosomal subunit",
        "classes": {"AMINOGLYCOSIDE"},
        "subclasses": {"GENTAMICIN", "AMINOGLYCOSIDE"},
    },
    "Amikacin": {
        "drug_class": "Aminoglycoside",
        "target": "30S ribosomal subunit",
        "classes": {"AMINOGLYCOSIDE"},
        "subclasses": {"AMIKACIN", "AMINOGLYCOSIDE"},
    },
    "Tigecycline": {
        "drug_class": "Glycylcycline",
        "target": "30S ribosomal subunit",
        "classes": {"TETRACYCLINE", "GLYCYLCYCLINE"},
        "subclasses": {"TIGECYCLINE"},
    },
}


def is_known_cause(drug: str, gene_class: str, gene_subclass: str) -> bool:
    """True if a detected gene's class/subclass is a curated cause for this drug."""
    d = DRUGS.get(drug)
    if not d:
        return False
    gc = (gene_class or "").upper()
    gs = (gene_subclass or "").upper()
    return gc in d["classes"] or gs in d["subclasses"]


def target_of(drug: str) -> str:
    return DRUGS.get(drug, {}).get("target", "unknown")


def drug_class_of(drug: str) -> str:
    return DRUGS.get(drug, {}).get("drug_class", "")
