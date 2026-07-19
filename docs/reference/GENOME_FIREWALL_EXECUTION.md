# 🧬 Genome Firewall — Execution Plan (20-Hour Hackathon)

**Challenge 06 · Hack-Nation 6th Global AI Hackathon · Powered by OpenAI**

> Predict which antibiotics will work / fail for a bacterial genome — *before* the lab results arrive — with **calibrated confidence**, an honest **no-call**, and **cited evidence**. Strictly defensive. Never designs or modifies organisms.

This doc is the single source of truth for what we're building and how. Read the whole thing once (~10 min), then jump to your role's section.

---

## 0. TL;DR (read this first)

We take a bacterial genome (FASTA) → detect known resistance genes/mutations (AMRFinderPlus) → run a small **calibrated logistic-regression model per antibiotic** → output **likely to work / likely to fail / no-call** with a confidence score and the exact genes behind it → show it in a **Streamlit app** with a mandatory "confirm with lab testing" disclaimer.

**We win on scientific honesty, not a high accuracy number:**
1. **Phylogenetic (grouped) train/test split** — not random. (This is the #1 thing judges check.)
2. **Calibrated confidence + real no-call** — the model knows when to stay silent.
3. **Honest evidence** — separate *known resistance gene* from *statistical association only*.

Scope discipline: **ONE species, 3–5 antibiotics, done well.** Do NOT claim universal coverage.

---

## 1. What we are building

Three modules (all required by the brief):

| # | Module | What it does | Output |
|---|--------|--------------|--------|
| **01** | **Genome Reader** | FASTA genome → feature vector via AMRFinderPlus | 0/1 table: which known AMR genes/mutations are present |
| **02** | **The Predictor** | Per-antibiotic model on those features + target gate + de-dup | For each drug: work / fail / no-call + calibrated confidence + evidence |
| **03** | **The Decision Report** | Streamlit/Gradio app | Per-drug report card + confidence + evidence category + lab-confirm disclaimer |

**In scope:** quality-checked FASTA (one reconstructed genome) → per-antibiotic prediction.
**Out of scope (do NOT build):** sample collection, reading DNA from blood, species ID, genome assembly, separating mixed samples. Our system starts *after* sequencing + assembly.

**Hard safety rule:** the tool only *predicts and explains resistance that already exists*. It must never suggest changes to an organism. State this out loud in the app and the pitch.

---

## 2. Scope decision — species & antibiotics

> ⚠️ **First action:** check the organizer's fixed challenge dataset. The brief says they provide **~1,000–3,000 genomes for ONE species + 3–5 predefined antibiotics + a grouped train/calibration/hidden-test split**. If so, the species and drugs are **chosen for us** — use theirs. The recommendation below is our fallback if we pick ourselves.

**Recommended species (fallback): *Klebsiella pneumoniae*** — a WHO-priority superbug, huge amount of lab AST data in BV-BRC, clear resistance genetics, and curated point mutations in AMRFinderPlus. (Backup: *E. coli*.)

**Recommended antibiotics (fallback, 4):**
| Antibiotic | Resistance mechanism | Why it's a good demo |
|---|---|---|
| Meropenem (carbapenem) | acquired genes: `blaKPC`, `blaNDM`, `blaOXA-48` | clean gene→resistance signal; the classic superbug story |
| Ciprofloxacin (fluoroquinolone) | **point mutations** `gyrA`, `parC` (+ `qnr`) | shows off `-O` point-mutation detection |
| Gentamicin (aminoglycoside) | modifying enzymes `aac`, `aph`, `aad` | multiple genes, good statistical case |
| Ceftazidime (cephalosporin) | ESBL genes `blaCTX-M` | shows the target-gate / class logic |

This mix intentionally covers **both** acquired-gene resistance and mutation-based resistance, so the demo isn't one-dimensional.

---

## 3. System architecture

```
  BV-BRC PATRIC_genomes_AMR.txt ──filter(species, drugs, LAB-measured only)──► labels y + genome_id list
                                                                                      │
  BV-BRC genomes/<id>.fna  ◄──── download just those ids ───────────────────────────┘
          │
          ▼
   [Module 01] AMRFinderPlus  -n <id>.fna -O Klebsiella --plus
          │                                        │
          ▼                                        ▼
   feature matrix X (0/1 per gene)     Class/Subclass  →  gene→drug knowledge base
          │                                        │  (used for honest evidence + target gate)
          ├──── de-dup / cluster genomes by sequence homology (Mash/MLST) ──► group ids
          │
          ▼
   [Module 02] per-drug logistic regression  (GROUPED split, calibrated)
          │  → P(resistant) → {work / fail / no-call} + target gate + OOD no-call
          ▼
   [Module 03] Streamlit report: per-drug call + confidence + evidence category
                                  + "⚠️ Confirm with standard lab testing"
```

---

## 4. The three winning principles (do NOT skip these)

These ARE the rubric. A polished app with a random split loses to a plain app that gets these right.

### 4.1 Phylogenetic (grouped) split — the big one
Bacteria are clonal, so a **random** split leaks near-identical genomes into both train and test → fake high score. We must **cluster genomes by sequence similarity and hold out whole clusters.**
- **Fast way:** `Mash`/`sourmash` sketch → cluster at a distance threshold (e.g. ~99.9% identity = same clone). Or group by **MLST sequence type** if available (free, no compute). Or use the **organizer's provided grouped split** if given.
- Implement with `StratifiedGroupKFold(groups=cluster_id)` — never a plain split.
- **Demo move:** show random-split score vs grouped-split score side by side, and explain the gap. This single table proves we understand the trap.

### 4.2 Calibration + no-call
- Calibrate probabilities on a **separate calibration split** using `CalibratedClassifierCV` (isotonic or sigmoid). Never calibrate on train or test.
- Report **Brier score** + **reliability diagram** (predicted confidence vs actual accuracy).
- **No-call fires on two triggers:**
  - **Low confidence:** P(resistant) near 0.5 (weak/conflicting evidence) → abstain.
  - **Out-of-distribution:** genome unlike anything in training (far from all clusters, or has unseen genes) → abstain with reason "novel lineage."
- Report **no-call rate + accuracy on the calls we kept** (risk–coverage). "22% no-call, 91% accuracy on the rest" beats "100% answered, 78%."

### 4.3 Honest evidence (known cause vs statistical)
Every prediction carries an **evidence category**:
- **(i) Known resistance gene/mutation** — feature present AND is a curated cause *for this drug class* (from AMRFinderPlus `Class`/`Subclass`). High trust, cite the gene.
- **(ii) Statistical association only** — model leaned on a feature that isn't a known cause for this drug. Flag as unconfirmed.
- **(iii) No known signal** — nothing found → lean to no-call; if we say "works," it must come from the **target gate**, not from mere absence of markers.
- **Rule:** a SHAP / feature-importance value does NOT prove biological cause. The AMRFinderPlus `Class/Subclass` mapping — not SHAP magnitude — decides the honesty category.

### 4.4 The target gate (cheap credibility)
Never output "likely to work" just because no resistance gene was found. Add a deterministic check: *is the drug's molecular target even present / is the species intrinsically resistant?* If the target is absent → never "works."

---

## 5. Tech stack

| Layer | Choice | Notes |
|---|---|---|
| Language | **Python 3.10+** | one repo, one venv/conda env |
| Bio tooling | **AMRFinderPlus** (bioconda) | `conda install -c bioconda ncbi-amrfinderplus`; `amrfinder -u` once |
| Data pull | **FTPS** from BV-BRC + `pandas` | `PATRIC_genomes_AMR.txt` + `.fna` files |
| Clustering | **Mash** or **sourmash** (or MLST) | for the grouped split / de-dup |
| ML | **scikit-learn** | LogisticRegression, CalibratedClassifierCV, StratifiedGroupKFold, metrics |
| Explainability | `shap` or model coefficients | *flashlight only* — cross-ref with known genes |
| App | **Streamlit** (recommended) or Gradio | brief requires one of these |
| LLM | **OpenAI API** ($50 credits/team) | report-writing layer: turn evidence → plain-language cited report; optional `gpt-image` evidence viz |

**OpenAI's role:** NOT the core prediction (that's classic ML). Use it to (a) generate the clear, plain-language, cited clinical-style report from the structured evidence, and (b) optionally visualize the evidence. Keep the actual call/confidence deterministic from the ML model.

---

## 6. Repo structure

```
genome-firewall/
├── data/
│   ├── raw/               # PATRIC_genomes_AMR.txt, downloaded .fna files
│   ├── amrfinder/         # AMRFinderPlus TSV outputs (or organizer precomputed)
│   └── processed/         # feature_matrix.parquet, labels.csv, clusters.csv
├── src/
│   ├── m01_genome_reader.py   # fasta -> amrfinder -> features
│   ├── m02_predictor.py       # train, calibrate, grouped-split, no-call, target gate
│   ├── clustering.py          # mash/MLST -> cluster_id (grouped split)
│   ├── evaluate.py            # balanced acc, recall R/S, F1, AUROC, PR-AUC, Brier, reliability
│   ├── drug_db.py             # antibiotic -> molecular target + known genes (from AMRFinderPlus class map)
│   └── report.py              # OpenAI: evidence -> plain-language cited report
├── app/
│   └── streamlit_app.py       # upload FASTA -> per-drug report cards + disclaimer
├── models/                    # saved calibrated models per drug
├── notebooks/                 # EDA, metrics plots
├── requirements.txt / environment.yml
└── README.md                  # how to run + what's covered / not covered
```

---

## 7. The 20-hour timeline

Designed for a small team working in parallel. Owners are by **role**, not name — assign in §8. Times are cumulative from H0 (kickoff).

| Phase | Hours | What happens | Owner(s) | Done when… |
|---|---|---|---|---|
| **P0 — Setup** | H0–H2 | Get organizer dataset; check for precomputed AMRFinderPlus. Create repo + env. Install AMRFinderPlus (`amrfinder -u`). Decide species/drugs. | All | env works, `amrfinder -l` runs, dataset located |
| **P1 — Data** | H2–H5 | Load `PATRIC_genomes_AMR.txt`, filter species+drugs+**lab-measured only**, map S/I/R → labels, download needed `.fna`. EDA: class balance per drug. | Data/Bio | `labels.csv` + genome files ready; per-drug counts known |
| **P2 — Features (M01)** | H4–H8 | Run AMRFinderPlus on all genomes (or load precomputed) → build 0/1 `feature_matrix`. Keep Type=AMR. Save `Class/Subclass` map. | Data/Bio | `feature_matrix.parquet` exists, joins to labels |
| **P3 — Clustering** | H5–H8 | Mash/sourmash (or MLST) → `cluster_id` per genome for grouped split. | Data/Bio + ML | every genome has a cluster_id |
| **P4 — Baseline model (M02)** | H8–H12 | Per-drug LogisticRegression on **grouped split**. Get one drug fully working end-to-end first, then loop all. | ML | predictions for all drugs on held-out grouped split |
| **P5 — Calibration + no-call** | H11–H15 | Calibrate on calibration split; add low-confidence + OOD no-call; add target gate. | ML | calibrated probs, no-call working, target gate live |
| **P6 — Evaluation** | H13–H16 | Metrics per drug: balanced acc, recall R & S separately, F1, AUROC, PR-AUC, Brier + reliability plot. **Random vs grouped comparison table.** | ML | metrics table + plots generated |
| **P7 — App (M03)** | H10–H17 | Streamlit: upload FASTA → run pipeline → per-drug cards (call, confidence, evidence category, cited genes) + **lab-confirm disclaimer**. | App | can upload a genome and get a full report |
| **P8 — OpenAI report layer** | H15–H18 | Evidence → plain-language cited report via OpenAI. Optional evidence viz. | App + ML | report reads clearly, cites real genes |
| **P9 — Polish + demo** | H18–H20 | README (coverage/limitations), rehearse 3-min demo, prep the honesty story, buffer for fires. | All | demo runs start-to-finish twice cleanly |

**Golden rule:** get **one drug fully end-to-end (data → feature → calibrated prediction → app card)** by ~H12. Everything after is repetition + polish. Do not build all modules in parallel to 80% — build one vertical slice to 100% first.

---

## 8. Team roles (assign names)

| Role | Owns | Skills |
|---|---|---|
| **Data/Bio** | Modules 01, data pull, clustering, feature matrix | Python, pandas, comfort with bio tools |
| **ML** | Module 02, calibration, no-call, evaluation, metrics | scikit-learn, model eval |
| **App/Report** | Module 03 Streamlit, OpenAI report layer, demo | Streamlit, API, UX |

If solo/two people: one person does Data/Bio+ML, the other App/Report; cut the deep-learning stretch entirely and lean on the organizer's precomputed AMRFinderPlus if available.

---

## 9. Deliverables checklist (mapped to what's graded)

- [ ] Repeatable path: FASTA → features (Module 01), documented
- [ ] Per-drug predictions: **work / fail / no-call** with calibrated confidence (Module 02)
- [ ] **De-dup / grouped split** applied and justified (threshold stated)
- [ ] **Target gate** implemented (no "works" from mere absence)
- [ ] Streamlit/Gradio app with per-drug report + evidence category (Module 03)
- [ ] **Mandatory "confirm with standard lab testing" message**
- [ ] Metrics: balanced accuracy, recall for R and S **separately**, F1, AUROC, PR-AUC per drug
- [ ] **Brier score + reliability plot**; no-call rate + accuracy on kept calls
- [ ] Generalization: results by genetically related group (grouped/hidden split)
- [ ] Honest explanations: known gene vs statistical association clearly separated
- [ ] Explicit statement of which species + antibiotics we cover / don't cover
- [ ] "Strictly defensive" framing stated in app + pitch

---

## 10. Definition of done / demo script (3 min)

1. **Frame it (20s):** "1M+ deaths/yr from resistance. Lab takes 1–3 days. We predict from the genome in seconds — honestly." State: strictly defensive, decision support only.
2. **Upload a real held-out genome (30s):** show per-drug cards appear.
3. **Show a confident call (30s):** meropenem → "likely to fail," high confidence, evidence = **known gene `blaKPC` detected** (category i). Cite it.
4. **Show a no-call (30s):** a drug where evidence is weak/OOD → "no-call: novel lineage / conflicting evidence." Explain why silence is a feature.
5. **Show honesty (40s):** the random-split vs grouped-split table + reliability plot. "Our real number is X, not the inflated Y most models report."
6. **Close (20s):** the mandatory lab-confirm disclaimer on screen. Coverage + limitations. "Defensive by construction."

---

## 11. Risks & ruthless cut list

| Risk | Mitigation |
|---|---|
| AMRFinderPlus install/run eats hours | Use organizer's **precomputed** results if provided; install in P0 in parallel |
| Class imbalance (few resistant cases for some drugs) | pick drugs with balance; use PR-AUC + balanced accuracy; drop a drug if hopeless |
| Clustering tooling is fiddly | fall back to **MLST-based grouping** or organizer's provided split |
| Running out of time | **cut deep-learning stretch, cut multimodal viz, cut extra drugs.** Never cut: grouped split, calibration/no-call, honest evidence, disclaimer |

**If behind at H15:** freeze scope to 2–3 drugs, one clean end-to-end path, and spend remaining time on the honesty story (grouped split table + reliability plot) — that's what scores.

---

## 12. First commands (P0)

```bash
# env
conda create -n genome-firewall python=3.10 -y
conda activate genome-firewall
conda install -c bioconda ncbi-amrfinderplus mash -y
amrfinder -u                 # download AMRFinderPlus DB (once)
amrfinder -l                 # list organisms with curated point mutations
pip install pandas scikit-learn shap streamlit openai matplotlib pyarrow

# grab labels (all species/drugs; we filter in code)
# from BV-BRC FTPS: ftps://ftp.bv-brc.org/RELEASE_NOTES/PATRIC_genomes_AMR.txt
# genomes: ftps://ftp.bv-brc.org/genomes/<genome_id>/<genome_id>.fna
```

---

*Questions / decisions to lock before H2: confirm organizer dataset & split, confirm species + drug list, assign roles.*
