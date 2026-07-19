---
title: Genome Firewall (E. coli)
emoji: 🧬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Genome Firewall — E. coli antibiotic-response predictor

Live deployment of the strong E. coli bundle: for one assembled *Escherichia coli*
genome it returns, per antibiotic, `likely to fail` / `likely to work` / `no-call`,
each with a calibrated confidence and an evidence category.

This Space runs **AMRFinderPlus** inside the container, so it accepts a real genome
upload (which Streamlit Community Cloud cannot do). The four calibrated models
(ciprofloxacin, ceftriaxone, gentamicin, ampicillin) were trained on 3,000 BV-BRC
genomes with Mash homology-grouped, leakage-audited splits.

> **Research prototype — not a clinical diagnostic.** Every result must be confirmed
> with standard laboratory antimicrobial-susceptibility testing.

## How it is built

The `Dockerfile` installs AMRFinderPlus and its database from bioconda, clones the
public app repository, and launches the Streamlit UI in E. coli bundle mode
(`GF_MODEL_BUNDLE` + `GF_AMRFINDER`). Source: https://github.com/justenm25/HackNation-6th

## Usage

Upload one assembled E. coli FASTA (`.fna`, `.fasta`, `.fa`). Do not upload FASTQ
reads, multiple genomes, or a non-E. coli sample.
