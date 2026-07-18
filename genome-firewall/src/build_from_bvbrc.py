"""
Build the training dataset from BV-BRC website CSV downloads (no Colab, no
AMRFinderPlus, Windows-friendly). BV-BRC already precomputes AMR genes + MLST.

Drop the three BV-BRC exports into data/raw/ (any of these name styles work):
  - genome AMR table   (e.g. BVBRC_genome_amr.csv) -> labels
  - specialty genes    (e.g. BVBRC_sp_gene.csv)    -> features (Antibiotic Resistance)
  - genome metadata    (e.g. BVBRC_genome.csv)     -> groups (MLST)

Outputs (data/processed/):
  labels.csv · features.parquet · clusters.csv · amr_gene_info.csv

Run:  python -m src.build_from_bvbrc      (from the genome-firewall/ project root)

Big files are streamed in chunks so this runs on a laptop.
"""
from __future__ import annotations
import glob
import os
import re
import pandas as pd

from src.contract import SUPPORTED_DRUGS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(HERE, "data", "raw")
PROC = os.path.join(HERE, "data", "processed")
DRUGS_L = {d.lower() for d in SUPPORTED_DRUGS}
CHUNK = 200_000


def _find(raw, must, exclude=()):
    """First csv in raw whose lowercase name contains all `must` and none of `exclude`."""
    for p in sorted(glob.glob(os.path.join(raw, "*.csv"))):
        n = os.path.basename(p).lower()
        if all(m in n for m in must) and not any(x in n for x in exclude):
            return p
    raise FileNotFoundError(f"No file in {raw} matching {must} (excluding {exclude}).")


def _col(cols, *cands):
    norm = {re.sub(r"[^a-z0-9]", "", c.lower()): c for c in cols}
    for cand in cands:
        key = re.sub(r"[^a-z0-9]", "", cand.lower())
        if key in norm:
            return norm[key]
        for k, orig in norm.items():
            if key and key in k:
                return orig
    return None


# Collapse allele-level / multi-source names into one canonical gene family.
# Order matters (specific carbapenemase OXA-48 before generic OXA, etc.).
_FAMILIES = [
    (r"KPC",                      "blaKPC",       "BETA-LACTAM", "CARBAPENEM"),
    (r"\bNDM",                    "blaNDM",       "BETA-LACTAM", "CARBAPENEM"),
    (r"\bVIM",                    "blaVIM",       "BETA-LACTAM", "CARBAPENEM"),
    (r"\bIMP\b|IMP-\d",           "blaIMP",       "BETA-LACTAM", "CARBAPENEM"),
    (r"OXA[- ]?(48|181|232|244|204)", "blaOXA-48", "BETA-LACTAM", "CARBAPENEM"),
    (r"\bGES",                    "blaGES",       "BETA-LACTAM", "CARBAPENEM"),
    (r"CTX[- ]?M",                "blaCTX-M",     "BETA-LACTAM", "CEPHALOSPORIN"),
    (r"\bSHV",                    "blaSHV",       "BETA-LACTAM", "CEPHALOSPORIN"),
    (r"\bTEM",                    "blaTEM",       "BETA-LACTAM", "CEPHALOSPORIN"),
    (r"\bCMY|\bDHA\b|\bACT\b|\bFOX\b|\bMIR\b|AmpC|\bCMH", "blaAmpC", "BETA-LACTAM", "CEPHALOSPORIN"),
    (r"\bOXA",                    "blaOXA",       "BETA-LACTAM", ""),
    (r"aac\(6.?\)-Ib-cr",         "aac(6')-Ib-cr","QUINOLONE",   "FLUOROQUINOLONE"),
    (r"\bqnr",                    "qnr",          "QUINOLONE",   "FLUOROQUINOLONE"),
    (r"oqx",                      "oqxAB",        "QUINOLONE",   "FLUOROQUINOLONE"),
    (r"qepA",                     "qepA",         "QUINOLONE",   "FLUOROQUINOLONE"),
    (r"\bgyrA",                   "gyrA",         "QUINOLONE",   "FLUOROQUINOLONE"),
    (r"\bparC",                   "parC",         "QUINOLONE",   "FLUOROQUINOLONE"),
    (r"armA",                     "armA",         "AMINOGLYCOSIDE", "AMIKACIN"),
    (r"\brmt",                    "rmt",          "AMINOGLYCOSIDE", "AMIKACIN"),
    (r"aac\(6",                   "aac(6')",      "AMINOGLYCOSIDE", "AMIKACIN"),
    (r"aac\(3",                   "aac(3)",       "AMINOGLYCOSIDE", "GENTAMICIN"),
    (r"aph\(|\baad|ant\(|strA|strB|\bAPH|\bANT\(", "aminoglycoside-other", "AMINOGLYCOSIDE", "GENTAMICIN"),
    (r"tet\(?X",                  "tet(X)",       "TETRACYCLINE", "TIGECYCLINE"),
    (r"tmexCD|tmvA",              "tmexCD",       "TETRACYCLINE", "TIGECYCLINE"),
    (r"tet[\(A-Z]",               "tet",          "TETRACYCLINE", ""),
    (r"\bsul\d",                  "sul",          "SULFONAMIDE",  ""),
    (r"dfrA|\bdfr",               "dfr",          "TRIMETHOPRIM", ""),
    (r"catA|catB|\bcml|floR",     "phenicol",     "PHENICOL",     ""),
    (r"mcr-\d",                   "mcr",          "COLISTIN",     ""),
]
_FAM_RE = [(re.compile(p, re.I), fam, c, s) for p, fam, c, s in _FAMILIES]


def normalize_gene(name: str):
    """Map any source/allele name -> (family, class, subclass) or (None, '', '')."""
    if not name:
        return None, "", ""
    for rx, fam, c, s in _FAM_RE:
        if rx.search(name):
            return fam, c, s
    return None, "", ""


def _infer_class(gene: str):
    _, c, s = normalize_gene(gene)
    return c, s


def build(raw=RAW, proc=PROC):
    os.makedirs(proc, exist_ok=True)

    # ---- labels (streamed) -------------------------------------------------
    amr_path = _find(raw, ["amr"])
    hdr = pd.read_csv(amr_path, nrows=0).columns
    c_gid = _col(hdr, "genome id", "genome_id")
    c_ab = _col(hdr, "antibiotic")
    c_ph = _col(hdr, "resistant phenotype", "phenotype")
    c_lab = _col(hdr, "laboratory typing method")
    c_ev = _col(hdr, "evidence")
    use = [c for c in {c_gid, c_ab, c_ph, c_lab, c_ev} if c]
    parts = []
    for ch in pd.read_csv(amr_path, dtype=str, usecols=use, chunksize=CHUNK):
        ch[c_ab] = ch[c_ab].str.lower().str.strip()
        ch = ch[ch[c_ab].isin(DRUGS_L)]
        if c_lab:  # lab-measured only
            ch = ch[ch[c_lab].notna() & (ch[c_lab].str.strip().str.len() > 0)]
        if c_ev:   # drop computational predictions
            ch = ch[~ch[c_ev].fillna("").str.contains("comput", case=False)]
        ph = ch[c_ph].str.strip().str.lower()
        ch = ch.assign(label=ph.map({"resistant": 1, "susceptible": 0}))
        ch = ch.dropna(subset=["label"])
        if len(ch):
            parts.append(ch[[c_gid, c_ab, "label"]])
    amr = pd.concat(parts, ignore_index=True)
    g = amr.groupby([c_gid, c_ab])["label"].mean().reset_index()
    g = g[g["label"] != 0.5]
    g["label"] = (g["label"] > 0.5).astype(int)
    labels = g.rename(columns={c_gid: "genome_id", c_ab: "drug"})
    labels["drug"] = labels["drug"].str.title()
    labels.to_csv(os.path.join(proc, "labels.csv"), index=False)
    keep = set(labels["genome_id"])
    print(f"labels.csv: {len(labels)} rows, {len(keep)} genomes")
    print(labels.groupby(["drug", "label"]).size().unstack(fill_value=0))

    # ---- features (streamed, Antibiotic Resistance only) -------------------
    sp_path = _find(raw, ["sp"], exclude=["amr"]) if glob.glob(os.path.join(raw, "*sp*")) \
        else _find(raw, ["gene"], exclude=["amr", "genome_amr"])
    hdr = pd.read_csv(sp_path, nrows=0).columns
    s_gid = _col(hdr, "genome id", "genome_id")
    s_gene = _col(hdr, "gene")
    s_prod = _col(hdr, "product")
    s_prop = _col(hdr, "property")
    s_cls = _col(hdr, "antibiotics class", "classification", "class")
    use = [c for c in {s_gid, s_gene, s_prod, s_prop} if c]
    pairs, gene_cls = set(), {}
    for ch in pd.read_csv(sp_path, dtype=str, usecols=use, chunksize=CHUNK):
        if s_prop:
            ch = ch[ch[s_prop].fillna("").str.contains("antibiotic resistance", case=False)]
        ch = ch[ch[s_gid].isin(keep)]
        if not len(ch):
            continue
        genes = ch[s_gene].fillna("").astype(str) if s_gene else [""] * len(ch)
        prods = ch[s_prod].fillna("").astype(str) if s_prod else [""] * len(ch)
        for gid_, gene_raw, prod_raw in zip(ch[s_gid], genes, prods):
            fam, c, s = normalize_gene(gene_raw)
            if fam is None:
                fam, c, s = normalize_gene(prod_raw)
            if fam is None:                       # keep only a clean short symbol
                g = gene_raw.strip()
                if 0 < len(g) <= 30 and " " not in g:
                    fam, c, s = g, "", ""
                else:
                    continue
            pairs.add((gid_, fam))
            gene_cls.setdefault(fam, (c, s))
    fdf = pd.DataFrame(list(pairs), columns=["genome_id", "gene"])
    fdf["present"] = 1
    X = (fdf.pivot_table(index="genome_id", columns="gene", values="present",
                         aggfunc="max", fill_value=0).astype("int8").reset_index())
    miss = keep - set(X["genome_id"])
    if miss:
        X = pd.concat([X, pd.DataFrame({"genome_id": list(miss)})], ignore_index=True).fillna(0)
    for c in X.columns:
        if c != "genome_id":
            X[c] = X[c].astype("int8")
    X.to_parquet(os.path.join(proc, "features.parquet"), index=False)
    print(f"features.parquet: {X.shape[0]} genomes x {X.shape[1]-1} genes")

    rows = []
    for gname in [c for c in X.columns if c != "genome_id"]:
        cls, sub = gene_cls.get(gname, ("", ""))
        if not cls:
            cls, sub = _infer_class(gname)
        rows.append({"gene": gname, "class": cls, "subclass": sub})
    pd.DataFrame(rows).to_csv(os.path.join(proc, "amr_gene_info.csv"), index=False)

    # ---- clusters (MLST) ---------------------------------------------------
    gpath = _find(raw, ["genome"], exclude=["amr"])
    hdr = pd.read_csv(gpath, nrows=0).columns
    m_gid = _col(hdr, "genome id", "genome_id")
    m_st = _col(hdr, "mlst", "sequence type")
    gm = pd.read_csv(gpath, dtype=str, usecols=[c for c in {m_gid, m_st} if c])
    gm = gm[gm[m_gid].isin(keep)]
    clusters, st2id, nxt = {}, {}, 0
    for _, r in gm.iterrows():
        st = str(r[m_st]) if m_st else ""
        st = re.search(r"\d+", st).group() if (st and re.search(r"\d+", st)) else ""
        key = f"ST{st}" if st else f"__solo_{r[m_gid]}"
        st2id.setdefault(key, len(st2id))
        clusters[r[m_gid]] = st2id[key]
    nxt = len(st2id)
    for gid_ in keep:              # genomes with no MLST row -> own cluster
        if gid_ not in clusters:
            clusters[gid_] = nxt; nxt += 1
    pd.DataFrame([{"genome_id": k, "cluster_id": v} for k, v in clusters.items()]).to_csv(
        os.path.join(proc, "clusters.csv"), index=False)
    print(f"clusters.csv: {len(set(clusters.values()))} groups (from MLST)")
    print("\nDone. Now run:  python -m src.train")


if __name__ == "__main__":
    build()
