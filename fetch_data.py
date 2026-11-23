"""Download every series in series.py from its primary source.

Banxico data come from the official SIE REST API, which needs a free token
(environment variable BANXICO_TOKEN). U.S. data come from FRED's public CSV
download, which needs no key.

Each run:
  * writes data/raw/<SERIES>.csv (date,value) for every series it fetched,
  * keeps the previous file untouched if a download fails,
  * appends one line per series to data/refresh_log.csv,
  * updates data/status.json with the time of the last fully successful run.

Usage:  BANXICO_TOKEN=... python fetch_data.py
"""
import csv
import io
import json
import os
import sys
import time
from datetime import date, datetime, timezone

import requests

from series import BANXICO, BANXICO_MISSING, FRED

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
LOG = os.path.join(ROOT, "data", "refresh_log.csv")
STATUS = os.path.join(ROOT, "data", "status.json")

HISTORY_START = "1990-01-01"
BANXICO_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{ids}/datos/{start}/{end}"
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
HEADERS = {"User-Agent": "mexico-peso-dashboard (student project; github actions)"}


def get(url, headers=None, tries=4):
    """GET with simple exponential back-off."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers={**HEADERS, **(headers or {})}, timeout=60)
            if r.status_code == 200:
                return r
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except requests.RequestException as e:
            last = str(e)
        time.sleep(2 ** i)
    raise RuntimeError(last)


def parse_number(s):
    s = str(s).strip().replace(",", "")
    if s in ("", ".", "N/E", "NA", "n.d."):
        return None
    v = float(s)
    return None if v == BANXICO_MISSING else v


def fetch_banxico_series(sid, token):
    """Return [(iso_date, value), ...] for one Banxico series."""
    url = BANXICO_URL.format(ids=sid, start=HISTORY_START, end=date.today().isoformat())
    payload = get(url, headers={"Bmx-Token": token, "Accept": "application/json"}).json()
    rows = []
    for s in payload["bmx"]["series"]:
        for d in s.get("datos", []):
            v = parse_number(d["dato"])
            if v is None:
                continue
            dd, mm, yyyy = d["fecha"].split("/")
            rows.append((f"{yyyy}-{mm}-{dd}", v))
    return rows


def fetch_fred(sid):
    text = get(FRED_URL.format(sid=sid)).text
    rows = []
    for rec in csv.DictReader(io.StringIO(text)):
        d = rec.get("observation_date") or rec.get("DATE")
        v = parse_number(rec.get(sid, ""))
        if d and v is not None:
            rows.append((d, v))
    return rows


def write_series(sid, rows):
    if not rows:
        raise RuntimeError("no observations returned")
    with open(os.path.join(RAW, f"{sid}.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "value"])
        w.writerows(rows)


def main():
    os.makedirs(RAW, exist_ok=True)
    run_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    results = {}  # sid -> (ok, n_obs, last_date, last_value, message)

    token = os.environ.get("BANXICO_TOKEN", "").strip()
    if not token:
        for sid in BANXICO:
            results[sid] = (False, 0, "", "", "BANXICO_TOKEN not set")
    else:
        for sid in BANXICO:  # one call per series: 9 calls, far below the 200 per 5 minutes limit
            try:
                rows = fetch_banxico_series(sid, token)
                write_series(sid, rows)
                results[sid] = (True, len(rows), rows[-1][0], rows[-1][1], "ok")
            except Exception as e:
                results[sid] = (False, 0, "", "", f"Banxico API error: {e}")

    for sid in FRED:
        try:
            rows = fetch_fred(sid)
            write_series(sid, rows)
            results[sid] = (True, len(rows), rows[-1][0], rows[-1][1], "ok")
        except Exception as e:
            results[sid] = (False, 0, "", "", str(e))

    new_log = not os.path.exists(LOG)
    with open(LOG, "a", newline="") as fh:
        w = csv.writer(fh)
        if new_log:
            w.writerow(["run_time_utc", "series", "status", "n_obs", "latest_date", "latest_value", "message"])
        for sid, (ok, n, d, v, msg) in results.items():
            w.writerow([run_time, sid, "OK" if ok else "FAILED", n, d, v, msg])

    status = {}
    if os.path.exists(STATUS):
        with open(STATUS) as fh:
            status = json.load(fh)
    all_ok = all(r[0] for r in results.values())
    status["last_attempt_utc"] = run_time
    status["last_attempt_ok"] = all_ok
    status["failed_series"] = [s for s, r in results.items() if not r[0]]
    if all_ok:
        status["last_successful_refresh_utc"] = run_time
        status["refresh_method"] = "Automated: GitHub Actions" if os.environ.get("GITHUB_ACTIONS") else "Automated: fetch_data.py run locally"
    with open(STATUS, "w") as fh:
        json.dump(status, fh, indent=2)

    for sid, (ok, n, d, v, msg) in results.items():
        print(f"{'OK    ' if ok else 'FAILED'} {sid:9s} n={n:<6} latest={d} {v}  {'' if ok else msg}")
    print(f"Run {run_time}: {'all series refreshed' if all_ok else 'some series failed, previous data kept'}")
    # A partial failure should not stop the dashboard from being rebuilt with
    # the last good data, but a total failure should be visible in Actions.
    if not any(r[0] for r in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
