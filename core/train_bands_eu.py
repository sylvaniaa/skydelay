"""Train the EUROPE delay-band model: P(on time / 15-60 / 60-120 / >120 min late).
Mirrors core/train_bands.py (US): same 4 classes (Gui et al. 2020), no undersampling,
HistGradientBoosting, k-fold target encoding (smoothing 50), same metrics.
Differences (state these in the report):
  - delay = actual arrival vs FILED arrival (flight plan), not the airline timetable
  - EUROCONTROL samples one month per quarter: Mar/Jun/Sep/Dec
  - temporal validation: train = 2023 sample months, test = Mar + Jun 2024
  - aircraft feature = ICAO type designator (B77W, A320...) instead of BTS family
  - weekday 0 = Monday (local time at origin)
Input : dataset/Eurocontrol/eu_model_base.csv.gz (from core/build_eu.py)
Output: data/model_bands_eu.joblib, data/model_meta_eu.json"""
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.model_selection import KFold

DS = os.path.expanduser("~/Documents/FYP/dataset/Eurocontrol")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
SAMPLE_N = 1500000
SMOOTH = 50
CLIP = (-60, 300)
MAX_AIRLINES = 250  # HistGradientBoosting categorical limit is < 255 categories
LABELS = ["On time (<=15 min)", "15-60 min late", "60-120 min late", "Over 120 min late"]
MONTH_MAP = {1: 12, 2: 3, 3: 3, 4: 3, 5: 6, 6: 6, 7: 6, 8: 9, 9: 9, 10: 9, 11: 12, 12: 12}
t0 = time.time()


def band(d):
    return np.select([d <= 15, d <= 60, d <= 120], [0, 1, 2], 3)


print("Reading eu_model_base.csv.gz ...")
cats = ["ADEP", "ADES", "airline_icao", "ac_type"]
df = pd.read_csv(os.path.join(DS, "eu_model_base.csv.gz"), dtype={c: "category" for c in cats})
df = df.dropna(subset=["arr_delay_min", "dist_nm", "ac_type"])
tr_all = df[df.ym <= 202312]
train = tr_all.sample(min(SAMPLE_N, len(tr_all)), random_state=42).copy()
test = df[df.ym >= 202401].copy()
n_train_all = len(tr_all)
del df, tr_all
for f in (train, test):
    for c in cats:
        f[c] = f[c].astype(str)
    f["y"] = f.arr_delay_min.clip(CLIP[0], CLIP[1])
    f["route"] = f.ADEP + "-" + f.ADES
print("train rows: %d (of %d) | test rows: %d | %.0fs" % (len(train), n_train_all, len(test), time.time() - t0))

air_list = train.airline_icao.value_counts().index[:MAX_AIRLINES].tolist()
type_list = train.ac_type.value_counts().index.tolist()
air_map = {v: i for i, v in enumerate(air_list)}
type_map = {v: i for i, v in enumerate(type_list)}
for f in (train, test):
    f["airline_idx"] = f.airline_icao.map(air_map).fillna(len(air_map)).astype(int)
    f["type_idx"] = f.ac_type.map(type_map).fillna(len(type_map)).astype(int)

KEYS = {"origin_te": "ADEP", "dest_te": "ADES", "route_te": "route", "airline_te": "airline_icao"}
gmean = float(train.y.mean())
print("global mean %.4f" % gmean)


def te_table(frame, key):
    g = frame.groupby(key)["y"].agg(["sum", "count"])
    return (g["sum"] + SMOOTH * gmean) / (g["count"] + SMOOTH)


te_tables = {}
for new_col, key in KEYS.items():
    oof = pd.Series(np.nan, index=train.index)
    for tr_idx, va_idx in KFold(5, shuffle=True, random_state=42).split(train):
        tab = te_table(train.iloc[tr_idx], key)
        oof.iloc[va_idx] = train.iloc[va_idx][key].map(tab).values
    train[new_col] = oof.fillna(gmean)
    full = te_table(train, key)
    te_tables[new_col] = {k: float(v) for k, v in full.items()}
    test[new_col] = test[key].map(full).fillna(gmean)
print("target encoding done | %.0fs" % (time.time() - t0))

FEATS = ["month", "weekday", "dep_hour", "dist_nm", "airline_idx", "type_idx",
         "origin_te", "dest_te", "route_te", "airline_te"]
CAT_IDX = [4, 5]
Xtr, Xte = train[FEATS], test[FEATS]
ytr = band(train.arr_delay_min.values)
yte = band(test.arr_delay_min.values)

print("Training 4-band classifier (5-10 min) ...")
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

# real delay distribution inside each band (for "typical delay", same method as US)
d = train.arr_delay_min.values
b = band(d)
band_mean = [float(d[b == k].mean()) for k in range(4)]
band_q = {str(k): np.percentile(d[b == k], np.arange(0, 101)).round(2).tolist() for k in (1, 2, 3)}
late_median = float(np.median(d[d > 15]))

joblib.dump(clf, os.path.join(OUT, "model_bands_eu.joblib"))
meta = {
    "region": "Europe", "source": "EUROCONTROL R&D (Mar/Jun/Sep/Dec 2023, Mar/Jun 2024)",
    "delay_definition": "actual arrival vs filed arrival (flight plan)",
    "features": FEATS, "cat_idx": CAT_IDX, "air_list": air_list, "type_list": type_list,
    "te_tables": te_tables, "global_mean": gmean, "smooth": SMOOTH, "clip": list(CLIP),
    "month_map": MONTH_MAP, "weekday_base": "0=Monday",
    "bands": {"labels": LABELS, "edges_min": [15, 60, 120], "train_prior": prior.tolist(),
              "band_mean_delay": band_mean, "band_quantiles": band_q,
              "late_median": late_median, "metrics": m},
}
with open(os.path.join(OUT, "model_meta_eu.json"), "w") as fh:
    json.dump(meta, fh)

print("\n=== TEST (Mar + Jun 2024), 4 delay bands, EUROPE ===")
for k in ("logloss_model", "logloss_prior_baseline", "accuracy_model",
          "accuracy_majority_baseline", "auc_ovr_macro", "auc_delayed15"):
    print("%-28s %.4f" % (k, m[k]))
print("\n%-20s %10s %10s" % ("band", "observed", "predicted"))
for k in range(4):
    print("%-20s %9.1f%% %9.1f%%" % (LABELS[k], 100 * m["observed_rate"][k], 100 * m["mean_predicted"][k]))
print("\nband mean delays (min):", [round(x, 1) for x in band_mean])
print("median delay of late flights: %.1f min" % late_median)
print("\nSaved model_bands_eu.joblib + model_meta_eu.json | %.0fs" % (time.time() - t0))
