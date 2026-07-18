# 🧬 Genome Firewall — An AI Defense System Against Superbugs

**Hack-Nation 6th Global AI Hackathon · Challenge 06 (powered by OpenAI)**

Genome Firewall reads a reconstructed bacterial genome and predicts, for each antibiotic,
whether it is **likely to fail / likely to work / no-call** — each with a **calibrated
confidence** and the **genes behind it**. It is strictly *defensive*: it only predicts and
explains resistance that already exists, and it never designs or modifies an organism.

Built and validated on **5,442 real _Klebsiella pneumoniae_ genomes** from BV-BRC.

## What it does
- **Genome Reader** — turns a genome's resistance genes into model features (BV-BRC / AMRFinderPlus-style annotations, normalized to gene families).
- **Predictor** — one calibrated logistic-regression model per antibiotic, with a molecular-target gate, an honest **no-call**, and bootstrap **confidence intervals**. Evaluated on a **grouped split by MLST** (held-out lineages), never random rows.
- **Decision Report** — a clinical Streamlit instrument: per-drug call, calibrated confidence, cited evidence, and a mandatory "confirm with lab testing" banner.

## Results (held-out, grouped split)
| Antibiotic | AUROC | PR-AUC |
|---|---|---|
| Ceftazidime | 0.79 | 0.97 |
| Ciprofloxacin | 0.72 | 0.92 |
| Meropenem | 0.64 | 0.68 |
| Gentamicin | 0.61 | 0.59 |
| Amikacin | 0.59 | 0.40 |
| Tigecycline | 0.53 | 0.18 |

The model is strongest for acquired-gene resistance (ESBLs → ceftazidime). Weak drugs are
**mutation-mediated** (gyrA/parC, porin loss) — mechanisms acquired-gene annotations don't
capture — so the system **withholds (no-call)** there rather than guessing.

## Run it
```bash
cd genome-firewall
python -m venv .venv && .venv/Scripts/activate     # Windows
pip install -r requirements.txt
streamlit run app/streamlit_app.py                 # open http://localhost:8501
```
The trained models ship in `models/artifacts/`, so the app runs out of the box.

By default the UI runs the clearly labeled collaborator Klebsiella demo. To connect the
same frontend to a trained leakage-safe E. coli bundle:

```bash
export GF_MODEL_BUNDLE=/absolute/path/to/ecoli-bundle
export GF_AMRFINDER=/absolute/path/to/amrfinder
streamlit run app/streamlit_app.py
```

The adapter at `app/backend_adapter.py` switches coverage, drug names, inference, evidence,
and evaluation artifacts without changing the visual frontend. It defaults to conservative
susceptibility calls; set `GF_SUSCEPTIBLE_POLICY=validated_low_risk` only for a threshold
policy validated and frozen with the bundle.

## Rebuild from data (optional)
Download three tables for *Klebsiella pneumoniae* from [bv-brc.org](https://www.bv-brc.org)
(AMR Phenotypes, Specialty Genes, Genomes) into `genome-firewall/data/raw/`, then:
```bash
python -m src.build_from_bvbrc    # CSVs -> data/processed/
python -m src.train               # trains per-drug models -> models/artifacts/
```
(The raw ~1.1 GB CSVs are git-ignored.)

## Layout
```
genome-firewall/
  src/    contract.py · build_from_bvbrc.py · drug_db.py · train.py · model.py · pipeline.py
  app/    streamlit_app.py · theme.py · charts.py · report.py
  data/processed/   labels.csv · features.parquet · clusters.csv · amr_gene_info.csv
  models/artifacts/ trained per-drug models + metrics
```

## Safety
Research prototype on public historical genomes. Every result must be confirmed by standard
laboratory testing; a trained professional makes the treatment decision. Defensive by
construction — no organism design or modification.
