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
