import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import KFold

DATASET = os.path.expanduser("~/Documents/FYP/dataset")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
os.makedirs(OUT, exist_ok=True)

SAMPLE_N = 3000000      # training rows sampled from 2023-2024
SMOOTH = 50             # shrinkage for target encoding (sparse routes -> global mean)
CLIP = (-60, 300)       # clip extreme delays for training/evaluation
t0 = time.time()

print("Reading flights_final.csv ...")
cols = ["Year", "Month", "DayOfWeek", "Reporting_Airline", "Origin", "Dest",
        "Distance", "CRSDepTime", "ArrDelay", "MODEL"]
df = pd.read_csv(os.path.join(DATASET, "flights_final.csv"), usecols=cols,
                 dtype={c: "category" for c in ["Reporting_Airline", "Origin", "Dest", "MODEL"]})
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

# ---- categorical indices (airline, aircraft family) ----
fam_list = train.family.value_counts().head(60).index.tolist()
air_list = sorted(train.Reporting_Airline.unique().tolist())
fam_map = {v: i for i, v in enumerate(fam_list)}
air_map = {v: i for i, v in enumerate(air_list)}
for f in (train, test):
    f["airline_idx"] = f.Reporting_Airline.map(air_map).fillna(len(air_map)).astype(int)
    f["family_idx"] = f.family.map(fam_map).fillna(len(fam_map)).astype(int)

# ---- target encoding (k-fold on train, full-train tables for test/app) ----
KEYS = {"origin_te": "Origin", "dest_te": "Dest", "route_te": "route", "airline_te": "Reporting_Airline"}
gmean = float(train.y.mean())


def te_table(frame, key):
    g = frame.groupby(key)["y"].agg(["sum", "count"])
    return (g["sum"] + SMOOTH * gmean) / (g["count"] + SMOOTH)


tables = {}
for new_col, key in KEYS.items():
    oof = pd.Series(np.nan, index=train.index)
    for tr_idx, va_idx in KFold(5, shuffle=True, random_state=42).split(train):
        tab = te_table(train.iloc[tr_idx], key)
        oof.iloc[va_idx] = train.iloc[va_idx][key].map(tab).values
    train[new_col] = oof.fillna(gmean)
    tables[new_col] = te_table(train, key)
    test[new_col] = test[key].map(tables[new_col]).fillna(gmean)
print("target encoding done | %.0fs" % (time.time() - t0))

FEATS = ["Month", "DayOfWeek", "sched_hour", "Distance", "airline_idx", "family_idx",
         "origin_te", "dest_te", "route_te", "airline_te"]
CAT_IDX = [FEATS.index("airline_idx"), FEATS.index("family_idx")]
Xtr, Xte = train[FEATS], test[FEATS]

# ---- regression: expected delay in minutes ----
print("Training regressor ...")
reg = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
                                    early_stopping=True, validation_fraction=0.1,
                                    categorical_features=CAT_IDX, random_state=42)
reg.fit(Xtr, train.y)
pred = reg.predict(Xte)
base = np.full(len(test), gmean)
metrics = {
    "reg_mae": float(mean_absolute_error(test.y, pred)),
    "reg_rmse": float(np.sqrt(mean_squared_error(test.y, pred))),
    "reg_r2": float(r2_score(test.y, pred)),
    "baseline_mae": float(mean_absolute_error(test.y, base)),
    "baseline_rmse": float(np.sqrt(mean_squared_error(test.y, base))),
}
print("regressor done | %.0fs" % (time.time() - t0))

# ---- classifier: P(arrival delay > 15 min) ----
print("Training classifier ...")
ytr_c = (train.ArrDelay > 15).astype(int)
yte_c = (test.ArrDelay > 15).astype(int)
clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_leaf_nodes=63,
                                     early_stopping=True, validation_fraction=0.1,
                                     categorical_features=CAT_IDX, random_state=42)
clf.fit(Xtr, ytr_c)
metrics["clf_auc"] = float(roc_auc_score(yte_c, clf.predict_proba(Xte)[:, 1]))
metrics["delay15_base_rate_test"] = float(yte_c.mean())
print("classifier done | %.0fs" % (time.time() - t0))

# ---- save ----
joblib.dump(reg, os.path.join(OUT, "model_reg.joblib"))
joblib.dump(clf, os.path.join(OUT, "model_clf.joblib"))
meta = {
    "features": FEATS, "cat_idx": CAT_IDX,
    "air_list": air_list, "fam_list": fam_list, "global_mean": gmean,
    "te_tables": {k: v.to_dict() for k, v in tables.items()},
    "metrics": metrics,
    "train": {"years": "2023-2024", "rows": int(len(train)), "test": "2025 Q1", "test_rows": int(len(test)),
              "target_clip": list(CLIP), "smooth": SMOOTH},
}
with open(os.path.join(OUT, "model_meta.json"), "w") as fh:
    json.dump(meta, fh)

print("\n=== TEST (Jan-Mar 2025) ===")
for k, v in metrics.items():
    print(k, round(v, 4))
print("saved to", OUT, "| total %.0fs" % (time.time() - t0))