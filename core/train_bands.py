"""Train the delay-band model: P(on time / 15-60 / 60-120 / >120 min late).
Same 4 classes as Gui et al. (2020), but WITHOUT undersampling, so the
probabilities match real-world frequencies. Uses exactly the same features,
training sample and target-encoding tables as core/train_model.py."""
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import KFold

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SAMPLE_N = 3000000
SMOOTH = 50
CLIP = (-60, 300)
LABELS = ["On time (<=15 min)", "15-60 min late", "60-120 min late", "Over 120 min late"]
t0 = time.time()


def band(d):
    return np.select([d <= 15, d <= 60, d <= 120], [0, 1, 2], 3)


with open(os.path.join(OUT, "model_meta.json")) as fh:
    meta = json.load(fh)

print("Reading flights_final.csv ...")
cols = ["Year", "Month", "DayOfWeek", "Reporting_Airline", "Origin", "Dest",
        "Distance", "CRSDepTime", "ArrDelay", "MODEL"]
cats = ["Reporting_Airline", "Origin", "Dest", "MODEL"]
df = pd.read_csv(os.path.join(DATASET, "flights_final.csv"), usecols=cols,
                 dtype={c: "category" for c in cats})
df = df.dropna(subset=["CRSDepTime", "ArrDelay", "MODEL"])
train = df[df.Year <= 2024].sample(SAMPLE_N, random_state=42).copy()
test = df[df.Year >= 2025].copy()
del df
for f in (train, test):
    for c in ("Reporting_Airline", "Origin", "Dest", "MODEL"):
        f[c] = f[c].astype(str)
    f["y"] = f.ArrDelay.clip(CLIP[0], CLIP[1])
    f["sched_hour"] = (f.CRSDepTime.astype(int) // 100) % 24
    f["family"] = f.MODEL.str.split("-").str[0].str.strip()
    f["route"] = f.Origin + "-" + f.Dest
print("train rows:", len(train), "| test rows:", len(test), "| %.0fs" % (time.time() - t0))

air_map = {v: i for i, v in enumerate(meta["air_list"])}
fam_map = {v: i for i, v in enumerate(meta["fam_list"])}
for f in (train, test):
    f["airline_idx"] = f.Reporting_Airline.map(air_map).fillna(len(air_map)).astype(int)
    f["family_idx"] = f.family.map(fam_map).fillna(len(fam_map)).astype(int)

KEYS = {"origin_te": "Origin", "dest_te": "Dest", "route_te": "route",
        "airline_te": "Reporting_Airline"}
gmean = float(train.y.mean())
print("global mean %.4f (saved model: %.4f)" % (gmean, meta["global_mean"]))


def te_table(frame, key):
    g = frame.groupby(key)["y"].agg(["sum", "count"])
    return (g["sum"] + SMOOTH * gmean) / (g["count"] + SMOOTH)


for new_col, key in KEYS.items():
    oof = pd.Series(np.nan, index=train.index)
    for tr_idx, va_idx in KFold(5, shuffle=True, random_state=42).split(train):
        tab = te_table(train.iloc[tr_idx], key)
        oof.iloc[va_idx] = train.iloc[va_idx][key].map(tab).values
    train[new_col] = oof.fillna(gmean)
    test[new_col] = test[key].map(meta["te_tables"][new_col]).fillna(gmean)
print("target encoding done | %.0fs" % (time.time() - t0))

FEATS = meta["features"]
CAT_IDX = meta["cat_idx"]
Xtr, Xte = train[FEATS], test[FEATS]
ytr = band(train.ArrDelay.values)
yte = band(test.ArrDelay.values)

print("Training 4-band classifier (several minutes) ...")
clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
                                     early_stopping=True, validation_fraction=0.1,
                                     categorical_features=CAT_IDX, random_state=42)
clf.fit(Xtr, ytr)
P = clf.predict_proba(Xte)
print("classifier done | %.0fs" % (time.time() - t0))

prior = np.bincount(ytr, minlength=4) / len(ytr)
P0 = np.tile(prior, (len(yte), 1))
m = {
    "logloss_model": float(log_loss(yte, P, labels=[0, 1, 2, 3])),
    "logloss_prior_baseline": float(log_loss(yte, P0, labels=[0, 1, 2, 3])),
    "accuracy_model": float(accuracy_score(yte, P.argmax(1))),
    "accuracy_majority_baseline": float((yte == 0).mean()),
    "auc_ovr_macro": float(roc_auc_score(yte, P, multi_class="ovr", average="macro")),
    "auc_delayed15": float(roc_auc_score(yte > 0, 1 - P[:, 0])),
    "observed_rate": [float((yte == k).mean()) for k in range(4)],
    "mean_predicted": [float(P[:, k].mean()) for k in range(4)],
}

joblib.dump(clf, os.path.join(OUT, "model_bands.joblib"))
meta["bands"] = {"labels": LABELS, "edges_min": [15, 60, 120],
                 "train_prior": prior.tolist(), "metrics": m}
with open(os.path.join(OUT, "model_meta.json"), "w") as fh:
    json.dump(meta, fh)

print("\n=== TEST (Jan-Mar 2025), 4 delay bands ===")
for k in ("logloss_model", "logloss_prior_baseline", "accuracy_model",
          "accuracy_majority_baseline", "auc_ovr_macro", "auc_delayed15"):
    print("%-28s %.4f" % (k, m[k]))
print("\n%-20s %10s %10s" % ("band", "observed", "predicted"))
for k in range(4):
    print("%-20s %9.1f%% %9.1f%%" % (LABELS[k], 100 * m["observed_rate"][k],
                                     100 * m["mean_predicted"][k]))
print("\nSaved model_bands.joblib and updated model_meta.json | %.0fs" % (time.time() - t0))
