"""
Train Genome Firewall models from the processed dataset.

Inputs  (data/processed/, produced by notebooks/01_build_dataset.ipynb):
  - features.parquet   genome_id + one 0/1 column per AMR gene/mutation
  - labels.csv         genome_id, drug, label (1=resistant/fail, 0=susceptible/work)
  - clusters.csv       genome_id, cluster_id   (homology groups for the honest split)
  - amr_gene_info.csv  gene, class, subclass   (optional; for evidence categorisation)

Outputs (models/artifacts/):
  per-drug calibrated model + bootstrap ensemble, feature columns, held-out metrics
  (grouped AND random split), reliability bins, demo samples, gene info, config.

Run:  python -m src.train           (from the genome-firewall/ project root)
"""
from __future__ import annotations
import json
import os
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import (balanced_accuracy_score, recall_score, f1_score,
                             roc_auc_score, average_precision_score, brier_score_loss)

from src.drug_db import DRUGS

# ---- tunables -------------------------------------------------------------
ABSTAIN_DELTA = 0.15     # no-call band: |P(R)-0.5| < DELTA -> withhold
N_BOOTSTRAP   = 25       # ensemble size for confidence intervals
TEST_FRACTION = 0.25     # held-out clusters
RANDOM_STATE  = 7

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROC = os.path.join(HERE, "data", "processed")
OUT  = os.path.join(HERE, "models", "artifacts")


def _load(proc=PROC):
    feats = pd.read_parquet(os.path.join(proc, "features.parquet"))
    labels = pd.read_csv(os.path.join(proc, "labels.csv"), dtype={"genome_id": str})
    clusters = pd.read_csv(os.path.join(proc, "clusters.csv"), dtype={"genome_id": str})
    feats["genome_id"] = feats["genome_id"].astype(str)
    gi_path = os.path.join(proc, "amr_gene_info.csv")
    gene_info = pd.read_csv(gi_path) if os.path.exists(gi_path) else pd.DataFrame(
        columns=["gene", "class", "subclass"])
    return feats, labels, clusters, gene_info


def _new_lr():
    return LogisticRegression(penalty="l2", C=1.0, class_weight="balanced",
                              max_iter=2000, solver="liblinear")


def _best_threshold(y, p):
    """Pick the decision threshold that maximises balanced accuracy (on val data)."""
    if len(set(y)) < 2:
        return 0.5
    cands = np.unique(np.round(p, 3))
    best, best_ba = 0.5, -1.0
    for t in cands:
        ba = balanced_accuracy_score(y, (p >= t).astype(int))
        if ba > best_ba:
            best_ba, best = ba, float(t)
    return best


def _metrics(y, p, tau=0.5):
    yhat = (p >= tau).astype(int)
    keep = np.abs(p - tau) >= ABSTAIN_DELTA          # calls we did NOT withhold
    out = {
        "balanced_acc_grouped": balanced_accuracy_score(y, yhat),
        "recall_resistant": recall_score(y, yhat, pos_label=1, zero_division=0),
        "recall_susceptible": recall_score(y, yhat, pos_label=0, zero_division=0),
        "f1": f1_score(y, yhat, zero_division=0),
        "brier": brier_score_loss(y, p),
        "no_call_rate": float(1 - keep.mean()),
        "accuracy_on_calls": float((yhat[keep] == y[keep]).mean()) if keep.any() else 0.0,
    }
    out["auroc"] = roc_auc_score(y, p) if len(set(y)) > 1 else 0.5
    out["pr_auc"] = average_precision_score(y, p) if len(set(y)) > 1 else float(np.mean(y))
    return out


def train(proc=PROC, out=OUT):
    os.makedirs(out, exist_ok=True)
    feats, labels, clusters, gene_info = _load(proc)
    gene_cols = [c for c in feats.columns if c != "genome_id"]
    feats = feats.merge(clusters, on="genome_id", how="left")
    feats["cluster_id"] = feats["cluster_id"].fillna(-1)

    # one grouped genome-level holdout (whole clusters held out) --------------
    gss = GroupShuffleSplit(n_splits=1, test_size=TEST_FRACTION, random_state=RANDOM_STATE)
    tr_idx, te_idx = next(gss.split(feats, groups=feats["cluster_id"]))
    train_ids = set(feats.iloc[tr_idx]["genome_id"]); test_ids = set(feats.iloc[te_idx]["genome_id"])
    fmap = feats.set_index("genome_id")[gene_cols]
    clmap = feats.set_index("genome_id")["cluster_id"].to_dict()

    metrics, reliability_y, reliability_p = [], [], []
    for drug in DRUGS:
        lab = labels[labels["drug"].str.lower() == drug.lower()]
        lab = lab.set_index("genome_id")["label"]
        tr = [g for g in train_ids if g in lab.index]
        te = [g for g in test_ids if g in lab.index]
        if len(tr) < 20 or len(set(lab.loc[tr])) < 2 or not te:
            print(f"[skip] {drug}: insufficient / single-class data")
            continue
        Xtr = fmap.loc[tr].values; ytr = lab.loc[tr].values
        Xte = fmap.loc[te].values; yte = lab.loc[te].values

        # pick a decision threshold on a grouped validation slice of TRAIN (never test)
        tau = 0.5
        try:
            g2 = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=RANDOM_STATE)
            fi, vi = next(g2.split(Xtr, ytr, groups=[clmap[g] for g in tr]))
            if len(set(ytr[fi])) > 1 and len(set(ytr[vi])) > 1:
                cvf = max(2, min(5, np.bincount(ytr[fi]).min()))
                calf = CalibratedClassifierCV(_new_lr(), cv=cvf, method="sigmoid").fit(Xtr[fi], ytr[fi])
                tau = _best_threshold(ytr[vi], calf.predict_proba(Xtr[vi])[:, 1])
        except Exception:
            pass

        # calibrated main model (refit on all train)
        cv = min(5, np.bincount(ytr).min())
        main = CalibratedClassifierCV(_new_lr(), cv=max(2, cv), method="sigmoid")
        main.fit(Xtr, ytr)
        p_te = main.predict_proba(Xte)[:, 1]

        # bootstrap ensemble -> confidence intervals at predict time
        boots = []
        rng = np.random.default_rng(RANDOM_STATE)
        for _ in range(N_BOOTSTRAP):
            bi = rng.integers(0, len(ytr), len(ytr))
            if len(set(ytr[bi])) < 2:
                continue
            m = _new_lr().fit(Xtr[bi], ytr[bi]); boots.append(m)

        # honest (grouped) metrics + inflated (random) baseline for the comparison
        mrow = _metrics(yte, p_te, 0.5); mrow["drug"] = drug; mrow["threshold"] = 0.5
        Xall = fmap.loc[tr + te].values; yall = lab.loc[tr + te].values
        rng2 = np.random.default_rng(RANDOM_STATE)
        perm = rng2.permutation(len(yall)); cut = int(0.8 * len(yall))
        rtr, rte = perm[:cut], perm[cut:]
        try:
            vcut = int(0.75 * len(rtr)); rfit, rval = rtr[:vcut], rtr[vcut:]
            rnd = CalibratedClassifierCV(_new_lr(), cv=3, method="sigmoid").fit(Xall[rfit], yall[rfit])
            rtau = _best_threshold(yall[rval], rnd.predict_proba(Xall[rval])[:, 1])
            p_rte = rnd.predict_proba(Xall[rte])[:, 1]
            mrow["balanced_acc_random"] = balanced_accuracy_score(yall[rte], (p_rte >= 0.5).astype(int))
        except Exception:
            rnd = _new_lr().fit(Xall[rtr], yall[rtr])
            mrow["balanced_acc_random"] = balanced_accuracy_score(yall[rte], rnd.predict(Xall[rte]))
        metrics.append(mrow)
        reliability_y.extend(list(yte)); reliability_p.extend(list(p_te))

        dump(main, os.path.join(out, f"{drug}__main.joblib"))
        dump(boots, os.path.join(out, f"{drug}__boot.joblib"))
        print(f"[ok] {drug}: grouped bal.acc {mrow['balanced_acc_grouped']:.2f} "
              f"(random {mrow['balanced_acc_random']:.2f}), n_test={len(te)}")

    # reliability bins (pooled) ----------------------------------------------
    rel = []
    yv, pv = np.array(reliability_y), np.array(reliability_p)
    for lo in np.arange(0.5, 1.0, 0.1):
        m = (np.abs(pv - 0.5) + 0.5 >= lo) & (np.abs(pv - 0.5) + 0.5 < lo + 0.1)
        if m.any():
            conf = (np.abs(pv[m] - 0.5) + 0.5).mean()
            acc = ((pv[m] >= 0.5).astype(int) == yv[m]).mean()
            rel.append({"confidence": float(conf), "accuracy": float(acc), "n": int(m.sum())})

    # held-out demo samples: diverse + interesting (not all gene-free) ---------
    test_list = [g for g in test_ids if g in fmap.index]
    counts = fmap.loc[test_list].sum(axis=1)
    carb = [c for c in ("blaKPC", "blaNDM", "blaOXA-48", "blaVIM", "blaIMP") if c in gene_cols]
    ctx = [c for c in ("blaCTX-M",) if c in gene_cols]
    picks = []
    def _add(gid):
        if gid not in picks:
            picks.append(gid)
    for gid in test_list:                                   # carbapenemase carriers
        if len(picks) >= 3: break
        if carb and fmap.loc[gid, carb].sum() > 0: _add(gid)
    for gid in test_list:                                   # ESBL carriers
        if len(picks) >= 5: break
        if ctx and fmap.loc[gid, ctx].sum() > 0: _add(gid)
    for gid in counts.sort_values(ascending=False).index:  # heavily armed
        if len(picks) >= 6: break
        _add(gid)
    for gid in counts[counts == 0].index:                  # clean / susceptible
        if len(picks) >= 8: break
        _add(gid)
    samples = {gid: {g: 1 for g in gene_cols if int(fmap.loc[gid, g]) == 1} for gid in picks}

    # persist -----------------------------------------------------------------
    json.dump(gene_cols, open(os.path.join(out, "feature_columns.json"), "w"))
    json.dump(metrics, open(os.path.join(out, "metrics.json"), "w"), indent=1)
    json.dump(rel, open(os.path.join(out, "reliability.json"), "w"), indent=1)
    json.dump(samples, open(os.path.join(out, "samples.json"), "w"), indent=1)
    gi = {str(r["gene"]): {"class": str(r.get("class", "")), "subclass": str(r.get("subclass", ""))}
          for _, r in gene_info.iterrows()}
    json.dump(gi, open(os.path.join(out, "gene_info.json"), "w"), indent=1)
    np.savez_compressed(os.path.join(out, "train_matrix.npz"),
                        X=fmap.loc[list(train_ids)].values.astype(np.int8),
                        ids=np.array(list(train_ids)))
    json.dump({"drugs": list(DRUGS), "abstain_delta": ABSTAIN_DELTA,
               "species": "Klebsiella pneumoniae"},
              open(os.path.join(out, "config.json"), "w"), indent=1)
    print(f"\nSaved {len(metrics)} drug models to {out}")
    return metrics


if __name__ == "__main__":
    train()
