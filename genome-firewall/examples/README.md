# Demo genome

`demo_ecoli_562.45650.fna` is the ready-to-upload genome used for the Genome Firewall
presentation.

| Field | Value |
|---|---|
| Source | BV-BRC public API |
| BV-BRC genome ID | `562.45650` |
| Organism | *Escherichia coli* strain EC_43 |
| GenBank assembly accession | `SHIQ00000000` |
| Assembly records | 98 contigs |
| Download method | `scripts/backend/acquire_bvbrc.py` via `/api/genome_sequence/` |
| SHA-256 after decompression | `7ce111af46f819405acd0a9947327309451b2bcb55acf5ee040276512df234c1` |

The file is an assembled genome in FASTA format, not raw sequencing reads. It is included
only to make the hackathon submission reproducible from a fresh clone. Its phenotype labels
were part of the fixed training cohort, so it is a functional demonstration input rather
than independent evidence of generalization. Model performance must be judged from the
homology-separated hidden-test metrics packaged with the model, not from this single demo.

To use it:

1. Run `./genome-firewall/launch.sh` from the repository root.
2. Open `http://localhost:8501`.
3. Upload `genome-firewall/examples/demo_ecoli_562.45650.fna`.
4. Select **Analyze genome**.

AMRFinderPlus analyzes the full assembly, so the demo may take a few minutes on a laptop.

## Precomputed hosted-demo path

Free Streamlit hosting cannot install AMRFinderPlus. For that environment, the bundle also
ships the raw AMRFinderPlus 4.2.7 result at:

```text
models/ecoli-bundle/precomputed/demo_ecoli_562.45650.tsv
```

`models/ecoli-bundle/precomputed_samples.json` registers it as
`demo_ecoli_562.45650`. In real bundle mode, choose **Sample genome** and then this sample;
the adapter sends the TSV directly to `genome_firewall.api.predict` with
`input_format="amrfinder_tsv"`. AMRFinderPlus is not invoked at runtime.

The TSV was generated with the same project environment used for model construction:

```text
AMRFinderPlus 4.2.7
NCBI database 2026-05-15.1
amrfinder -n examples/demo_ecoli_562.45650.fna -O Escherichia -o demo_ecoli_562.45650.tsv
```

SHA-256 of the raw TSV:

```text
0a5d157a303ab7f62a72159d0212e21516453236c5261db307a03da82943aebc
```
