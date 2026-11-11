"""City / airport photos for airport pages.
Wikidata: airport by IATA code (P238) -> city it serves (P931) -> image (P18); falls back to the airport's own image.
Wikimedia Commons API: thumbnail URL + author + licence. Stores links and credits only (no downloads): data/city_photos.csv"""
import csv
import json
import os
import re
import time
import urllib.parse
import urllib.request

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "data", "city_photos.csv")
UA = {"User-Agent": "SkyDelay/1.0 (UTP final year project, flight delay study)", "Accept": "application/json"}
BAD = re.compile(r"montage|collage|mosaic|composite|collection|map|logo|flag|coat.of.arms|seal|\.svg$", re.I)


def get(url):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=90) as r:
                return json.load(r)
        except Exception as e:
            print("  retry", i + 1, getattr(e, "code", "") or type(e).__name__)
            wait = 4 * (i + 1)
            if getattr(e, "code", None) == 429:
                try:
                    wait = max(int(e.headers.get("Retry-After", 0)), 15 * (i + 1))
                except Exception:
                    wait = 15 * (i + 1)
            time.sleep(wait)
    return None


def _claims(ent, prop):
    cs = (ent.get("claims") or {}).get(prop) or []
    cs = sorted(cs, key=lambda c: {"preferred": 0, "normal": 1}.get(c.get("rank"), 2))
    out = []
    for c in cs:
        if c.get("rank") == "deprecated":
            continue
        v = ((c.get("mainsnak") or {}).get("datavalue") or {}).get("value")
        if v is not None:
            out.append(v)
    return out


def _entities(ids):
    api = "https://www.wikidata.org/w/api.php"
    ents, ids = {}, list(dict.fromkeys(ids))
    for i in range(0, len(ids), 50):
        d = get(api + "?action=wbgetentities&format=json&props=claims&ids=" + "|".join(ids[i:i + 50]))
        if d is None or "entities" not in d:
            return None
        ents.update(d["entities"])
        time.sleep(0.5)
    return ents


def wikidata(codes):
    """Wikidata action API (SPARQL endpoint rate-limits us): P238 search -> claims P18 / P931 -> city P18."""
    api = "https://www.wikidata.org/w/api.php"
    d = get(api + "?action=query&format=json&list=search&srlimit=100&srsearch="
            + urllib.parse.quote("haswbstatement:" + "|".join(f"P238={c}" for c in codes)))
    if d is None:
        return None
    qs = [h["title"] for h in d.get("query", {}).get("search", [])]
    ents = _entities(qs)
    if ents is None:
        return None
    airport, cities = {}, {}
    for c in codes:
        for q in qs:
            e = ents.get(q) or {}
            if c in [str(v).upper() for v in _claims(e, "P238")]:
                airport[c] = e
                cities[c] = [v["id"] for v in _claims(e, "P931") if isinstance(v, dict) and "id" in v]
                break
    cents = _entities([q for v in cities.values() for q in v]) if any(cities.values()) else {}
    if cents is None:
        return None
    fp = lambda f: {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/" + urllib.parse.quote(f)}
    rows = []
    for c, e in airport.items():
        r = {"iata": {"value": c}}
        a_img = _claims(e, "P18")
        if a_img:
            r["aImg"] = fp(a_img[0])
        for q in cities.get(c, []):
            c_img = _claims(cents.get(q) or {}, "P18")
            if c_img:
                r["cImg"] = fp(c_img[0])
                break
        rows.append(r)
    return rows


def commons(files):
    out = {}
    for i in range(0, len(files), 40):
        chunk = files[i:i + 40]
        url = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&prop=imageinfo"
               "&iiprop=url|extmetadata&iiurlwidth=1400&titles=" + urllib.parse.quote("|".join("File:" + f for f in chunk)))
        d = get(url) or {}
        q = d.get("query", {})
        back = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in q.get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]
            md = ii.get("extmetadata") or {}
            t = back.get(p.get("title", ""), p.get("title", ""))
            t = t[5:] if t.startswith("File:") else t
            artist = re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", "")).strip()
            out[t] = {"url": ii.get("thumburl") or ii.get("url"), "page": ii.get("descriptionurl"),
                      "author": re.sub(r"\s+", " ", artist)[:80], "license": (md.get("LicenseShortName") or {}).get("value", "")}
        time.sleep(1)
        print(f"[photos] commons {min(i + 40, len(files))}/{len(files)}")
    return out


def main():
    ap = pd.read_csv(os.path.join(BASE, "data", "home_airports.csv"))
    codes = sorted(set(ap.code.dropna().astype(str)))
    have = {}
    if os.path.exists(OUT):
        old = pd.read_csv(OUT)
        have = {r.code: list(r) for r in old.itertuples(index=False)}
    todo = [c for c in codes if c not in have]
    print(f"[photos] already have {len(have)}, looking up {len(todo)}")
    pick, failed = {}, []
    for i in range(0, len(todo), 25):
        rows = wikidata(todo[i:i + 25])
        if rows is None:
            failed += todo[i:i + 25]
            continue
        for r in rows:
            c = r["iata"]["value"]
            for key, rank, kind in (("cImg", 0, "city"), ("aImg", 1, "airport")):
                if key not in r:
                    continue
                f = urllib.parse.unquote(r[key]["value"].rsplit("/", 1)[-1])
                if BAD.search(f):
                    continue
                if c not in pick or rank < pick[c][0]:
                    pick[c] = (rank, f, kind, "")
        print(f"[photos] wikidata {min(i + 25, len(todo))}/{len(todo)}, picked {len(pick)}")
        time.sleep(2)
    if failed:
        print("[photos] failed batches (rerun to retry):", " ".join(failed))
    meta = commons(sorted({v[1] for v in pick.values()}))
    for c, (rank, f, kind, city) in pick.items():
        m = meta.get(f)
        if m and m["url"]:
            have[c] = [c, kind, city, f, m["url"], m["page"], m["author"], m["license"]]
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["code", "kind", "city", "file", "url", "page", "author", "license"])
        for c in sorted(have):
            w.writerow(have[c])
    print(f"[photos] now {len(have)} of {len(codes)} airports -> {OUT}")


if __name__ == "__main__":
    main()
