"""Build docs/index.html from the raw series in data/raw.

All transformations happen here, in one place, so they can be audited:
  * year-over-year growth, 12-month rolling sums, unit conversions,
  * rebasing the real exchange rate to its 1995-present mean = 100,
  * the Banxico-Fed policy rate differential and the 10-year yield spread,
  * 21-business-day realized volatility of USD/MXN.

The page is a single static HTML file (Plotly.js from a CDN) so it can be
served by GitHub Pages and opened offline.
"""
import csv
import html
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from series import ALL_SERIES, BANXICO_MISSING, RER_START, SAMPLE_START

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "processed")
DOCS = os.path.join(ROOT, "docs")

C1, C2, C3 = "#2a78d6", "#eb6834", "#1baf7a"  # validated categorical slots 1-3
GRID, INK2 = "#e7e6e2", "#52514e"


# --------------------------------------------------------------------------- data
def load(sid):
    df = pd.read_csv(os.path.join(RAW, f"{sid}.csv"), parse_dates=["date"])
    df = df[df["value"] != BANXICO_MISSING].dropna()
    return df.set_index("date")["value"].sort_index()


def step_daily(s, end):
    """Expand a step series (policy rates) to calendar-daily values."""
    idx = pd.date_range(s.index.min(), end, freq="D")
    return s.reindex(idx).ffill()


def monthly(s):
    """Put a monthly series on a complete month-start calendar so that gaps
    (e.g. the U.S. CPI for Oct 2025, never collected because of the federal
    shutdown) stay as gaps instead of shifting later months."""
    return s.asfreq("MS")


def yoy(s):
    s = monthly(s)
    return (s / s.shift(12) - 1) * 100


def build_data():
    raw = {sid: load(sid) for sid in ALL_SERIES}
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    out, latest = {}, {}

    # 1. USD/MXN FIX
    fx = raw["SF43718"]
    out["fx"] = fx[fx.index >= SAMPLE_START]

    # 2. Real exchange rate, rebased to its 1995-present mean = 100
    rer = raw["SR28"][raw["SR28"].index >= RER_START]
    rer_mean = rer.mean()
    out["rer"] = rer / rer_mean * 100

    # 3. Policy rates and differential (Fed = midpoint of target range)
    end = max(today, raw["SF61745"].index.max())
    bmx = step_daily(raw["SF61745"], end)
    fed = step_daily((raw["DFEDTARU"] + raw["DFEDTARL"]).dropna() / 2, end)
    rates = pd.DataFrame({"banxico": bmx, "fed": fed}).dropna()
    rates = rates[rates.index >= SAMPLE_START]
    rates["diff"] = rates["banxico"] - rates["fed"]
    # keep only change points (plus the last day) so the page stays light
    chg = rates.ne(rates.shift()).any(axis=1)
    chg.iloc[-1] = True
    out["rates"] = rates[chg]

    # 4. Inflation: Mexico (published YoY) and U.S. (YoY computed from NSA CPI)
    mx_inf = raw["SP30578"]
    us_inf = yoy(raw["CPIAUCNS"]).dropna()
    infl = pd.DataFrame({"mx": monthly(mx_inf), "us": us_inf})
    out["infl"] = infl[infl.index >= SAMPLE_START]

    # 5. Trade balance: 12-month rolling sums, USD billions
    tb = pd.DataFrame({"total": monthly(raw["SE28294"]), "oil": monthly(raw["SE36600"]), "nonoil": monthly(raw["SE35403"])})
    tb12 = tb.rolling(12).sum() / 1e6  # thousands of USD -> billions
    out["trade"] = tb12[tb12.index >= SAMPLE_START].dropna()

    # 6. Automotive exports: 12-month rolling sum, USD billions, and YoY of that sum
    auto = monthly(raw["SE28442"])
    auto12 = auto.rolling(12).sum() / 1e6
    out["auto"] = pd.DataFrame({"sum12": auto12, "yoy12": yoy(auto12)})
    out["auto"] = out["auto"][out["auto"].index >= SAMPLE_START].dropna()

    # 7. 10-year yields and spread (monthly averages; Bono M has no data in months without an auction)
    y = pd.DataFrame({"mx": raw["SF30057"], "us": raw["GS10"]}).dropna()
    y["spread"] = y["mx"] - y["us"]
    out["yields"] = y[y.index >= SAMPLE_START]

    # 8. Realized volatility: std of daily log returns over 21 business days, annualized
    r = np.log(fx).diff()
    vol = (r.rolling(21).std() * np.sqrt(252) * 100).dropna()
    vol = vol[vol.index >= SAMPLE_START]
    carry = rates["diff"].reindex(vol.index, method="ffill")
    out["vol"] = pd.DataFrame({"vol": vol, "carry": carry})

    # Latest raw observation of every series (used for the verification table)
    for sid, s in raw.items():
        latest[sid] = (s.index.max().strftime("%Y-%m-%d"), float(s.iloc[-1]), len(s))
    return raw, out, latest, rer_mean


# ------------------------------------------------------------------------ helpers
def ser(s, nd=4):
    return {"x": [d.strftime("%Y-%m-%d") for d in s.index], "y": [None if pd.isna(v) else round(float(v), nd) for v in s.values]}


def fmt_date(ts, freq):
    ts = pd.Timestamp(ts)
    if freq == "M":
        return ts.strftime("%b %Y")
    return ts.strftime("%d %b %Y")


def pct_change(s, periods):
    return (s.iloc[-1] / s.iloc[-1 - periods] - 1) * 100


def read_status():
    p = os.path.join(ROOT, "data", "status.json")
    return json.load(open(p)) if os.path.exists(p) else {}


def read_log(n_runs=8):
    p = os.path.join(ROOT, "data", "refresh_log.csv")
    if not os.path.exists(p):
        return []
    rows = list(csv.DictReader(open(p)))
    runs = {}
    for r in rows:
        runs.setdefault(r["run_time_utc"], []).append(r)
    out = []
    for t in sorted(runs)[-n_runs:][::-1]:
        rs = runs[t]
        ok = sum(r["status"] == "OK" for r in rs)
        failed = [r["series"] for r in rs if r["status"] != "OK"]
        out.append({"time": t, "ok": ok, "n": len(rs), "failed": failed})
    return out


def read_verification():
    p = os.path.join(ROOT, "verification", "checks.csv")
    return list(csv.DictReader(open(p))) if os.path.exists(p) else []


# ---------------------------------------------------------------------- the page
def build():
    raw, d, latest, rer_mean = build_data()
    os.makedirs(PROC, exist_ok=True)
    os.makedirs(DOCS, exist_ok=True)
    os.makedirs(os.path.join(DOCS, "data"), exist_ok=True)
    for k, v in d.items():
        v.to_csv(os.path.join(PROC, f"{k}.csv"), index_label="date")
        v.to_csv(os.path.join(DOCS, "data", f"{k}.csv"), index_label="date")  # served next to the page

    with open(os.path.join(ROOT, "data", "latest_observations.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["series", "name", "source", "latest_date", "latest_value", "n_obs"])
        for sid, (dt, v, n) in latest.items():
            w.writerow([sid, ALL_SERIES[sid]["name"], ALL_SERIES[sid]["source"], dt, v, n])

    fx, rer, rates, infl = d["fx"], d["rer"], d["rates"], d["infl"]
    trade, auto, ylds, vol = d["trade"], d["auto"], d["yields"], d["vol"]

    # ---- headline numbers
    fx_now, fx_1y = fx.iloc[-1], (fx.iloc[-1] / fx[fx.index <= fx.index[-1] - pd.DateOffset(years=1)].iloc[-1] - 1) * 100
    rer_now = rer.iloc[-1]
    rer_rank = (rer < rer_now).mean() * 100  # share of months with a stronger real peso
    diff_now = rates["diff"].iloc[-1]
    infl_last = infl.dropna()
    inf_mx, inf_us = infl_last["mx"].iloc[-1], infl_last["us"].iloc[-1]
    tb_now = trade.iloc[-1]
    auto_now = auto.iloc[-1]
    y_now = ylds.iloc[-1]
    vol_now, vol_med = vol["vol"].iloc[-1], vol["vol"].median()
    ratio = diff_now / vol_now

    # ---- auto-generated reading (states facts and simple comparisons only)
    stronger = "stronger" if rer_now < 100 else "weaker"
    reading = [
        f"<b>Valuation.</b> The real exchange rate is {abs(rer_now - 100):.0f}% {'below' if rer_now < 100 else 'above'} its 1995&ndash;present average, so the peso is "
        f"<b>{stronger}</b> in real terms than usual; it was this strong or stronger in only {rer_rank:.0f}% of months since 1995. "
        f"In nominal terms USD/MXN is {fx_now:.2f}, {'up' if fx_1y > 0 else 'down'} {abs(fx_1y):.1f}% over the past year ({'peso weaker' if fx_1y > 0 else 'peso stronger'}).",
        f"<b>Carry.</b> Banxico's target rate exceeds the Fed's by {diff_now:.2f} percentage points. By covered interest parity this is roughly the annual "
        f"forward premium on USD/MXN, i.e. the yearly cost of hedging a peso receivable by selling pesos forward (or the gain from hedging a peso payable).",
        f"<b>Inflation.</b> Mexican inflation is {inf_mx:.2f}% versus {inf_us:.2f}% in the U.S. (latest common month). A positive gap erodes the peso's real value "
        f"unless the nominal rate depreciates by a similar amount.",
        f"<b>Trade.</b> Over the last 12 months the non-oil goods balance was US${tb_now['nonoil']:.1f} bn and the oil balance US${tb_now['oil']:.1f} bn. "
        f"Automotive exports totaled US${auto_now['sum12']:.0f} bn, {auto_now['yoy12']:+.1f}% versus the previous 12 months.",
        f"<b>Risk.</b> The 10-year Bono M&ndash;Treasury spread is {y_now['spread']:.2f} pp. Realized USD/MXN volatility is {vol_now:.1f}% (sample median {vol_med:.1f}%), "
        f"so the carry earned per unit of risk is {ratio:.2f}. A low ratio means an unhedged position is paid little for the currency risk it carries.",
    ]

    finding = (f"The peso is {'strong' if rer_now < 100 else 'weak'} in real terms, "
               f"and the carry {'pays little' if ratio < 0.5 else 'pays well'} for the currency risk")

    def meta(*sids):
        return [ALL_SERIES[s] for s in sids]

    charts = [
        {
            "id": "c_fx", "section": "Exchange rate", "title": "USD/MXN exchange rate (FIX)",
            "units": "Mexican pesos per U.S. dollar", "freq": "Daily (business days)",
            "convention": "Quoted as pesos per dollar (USD/MXN). A <b>higher</b> number means a <b>weaker</b> peso.",
            "transform": "None; FIX as published by Banxico.",
            "latest": f"{fx_now:.4f}", "latest_date": fmt_date(fx.index[-1], "D"), "srcs": meta("SF43718"),
            "traces": [{"name": "USD/MXN", "color": C1, **ser(fx)}],
            "yfmt": ".2f", "hover": "%{y:.4f} MXN per USD",
        },
        {
            "id": "c_rer", "section": "Exchange rate", "title": "Real exchange rate of the peso",
            "units": "Index, 1995&ndash;present average = 100", "freq": "Monthly",
            "convention": "Banxico's definition: foreign prices in pesos divided by Mexican prices, against 111 countries. "
                          "<b>Above 100</b> = peso cheaper than average (real depreciation); <b>below 100</b> = peso dearer than average (real appreciation).",
            "transform": f"Rebased: published index (1990 = 100) divided by its Jan 1995&ndash;latest mean ({rer_mean:.1f}) &times; 100. Sample starts 1995, the first full year of the float.",
            "latest": f"{rer_now:.1f}", "latest_date": fmt_date(rer.index[-1], "M"), "srcs": meta("SR28"),
            "traces": [{"name": "Real exchange rate", "color": C1, **ser(rer, 2)}],
            "ref": 100, "ref_label": "1995\u2013present average = 100", "yfmt": ".0f", "hover": "%{y:.1f}",
        },
        {
            "id": "c_rates", "section": "Carry and inflation", "title": "Policy rates and the carry",
            "units": "Percent per year", "freq": "Daily (changes on decision dates)",
            "convention": "Differential = Banxico target rate minus the midpoint of the Fed funds target range. By covered interest parity it approximates the annualized forward premium on USD/MXN.",
            "transform": "Fed midpoint = (upper + lower limit) / 2. Rates carried forward between decisions.",
            "latest": f"{diff_now:.2f} pp", "latest_date": fmt_date(rates.index[-1], "D"), "srcs": meta("SF61745", "DFEDTARU", "DFEDTARL"),
            "traces": [
                {"name": "Banxico target", "color": C1, "shape": "hv", **ser(rates["banxico"], 2)},
                {"name": "Fed funds (midpoint)", "color": C2, "shape": "hv", **ser(rates["fed"], 3)},
                {"name": "Differential", "color": C3, "shape": "hv", "dash": "dot", **ser(rates["diff"], 3)},
            ],
            "ref": 0, "yfmt": ".0f", "hover": "%{y:.2f}%",
        },
        {
            "id": "c_infl", "section": "Carry and inflation", "title": "Headline inflation: Mexico vs. United States",
            "units": "Percent, year over year", "freq": "Monthly",
            "convention": "Shaded band: Banxico's 3% target with its &plusmn;1 pp variability interval.",
            "transform": "Mexico: annual INPC inflation as published. U.S.: computed as 12-month % change of the non-seasonally-adjusted CPI-U (the same basis as Mexico's figure). BLS never collected the October 2025 CPI (federal shutdown), so U.S. inflation for Oct 2025 and Oct 2026 cannot be computed and is left blank.",
            "latest": f"{inf_mx:.2f}% vs {inf_us:.2f}%", "latest_date": fmt_date(infl_last.index[-1], "M"), "srcs": meta("SP30578", "CPIAUCNS"),
            "traces": [
                {"name": "Mexico (INPC)", "color": C1, **ser(infl["mx"].loc[:infl["mx"].last_valid_index()], 2)},
                {"name": "United States (CPI-U)", "color": C2, **ser(infl["us"].loc[:infl["us"].last_valid_index()], 2)},
            ],
            "band": [2, 4], "yfmt": ".0f", "hover": "%{y:.2f}%",
        },
        {
            "id": "c_trade", "section": "Trade", "title": "Goods trade balance: oil vs. non-oil",
            "units": "U.S. dollars, billions, rolling 12-month sum", "freq": "Monthly",
            "convention": "Positive = surplus. Non-oil is dominated by manufacturing; oil is now a deficit because Mexico imports refined fuels.",
            "transform": "Monthly balances (thousands of USD) summed over the latest 12 months and divided by 10<sup>6</sup>. The rolling sum removes seasonality.",
            "latest": f"{tb_now['nonoil']:.1f} / {tb_now['oil']:.1f}", "latest_date": fmt_date(trade.index[-1], "M"), "srcs": meta("SE35403", "SE36600", "SE28294"),
            "traces": [
                {"name": "Non-oil", "color": C1, **ser(trade["nonoil"], 2)},
                {"name": "Oil", "color": C2, **ser(trade["oil"], 2)},
                {"name": "Total", "color": C3, "dash": "dot", **ser(trade["total"], 2)},
            ],
            "ref": 0, "yfmt": ".0f", "hover": "US$%{y:.1f} bn",
        },
        {
            "id": "c_auto", "section": "Trade", "title": "Automotive manufacturing exports",
            "units": "U.S. dollars, billions, rolling 12-month sum", "freq": "Monthly",
            "convention": "Mexico's largest export and the channel most exposed to U.S. tariffs and the USMCA review. Roughly 80% of Mexico's exports go to the U.S.",
            "transform": "Monthly exports (thousands of USD) summed over 12 months, divided by 10<sup>6</sup>. Latest-value badge also shows % change vs. the prior 12 months.",
            "latest": f"US${auto_now['sum12']:.0f} bn ({auto_now['yoy12']:+.1f}%)", "latest_date": fmt_date(auto.index[-1], "M"), "srcs": meta("SE28442"),
            "traces": [{"name": "Automotive exports, 12-month sum", "color": C1, **ser(auto["sum12"], 2)}],
            "yfmt": ".0f", "hover": "US$%{y:.1f} bn",
        },
        {
            "id": "c_yields", "section": "Risk and hedging", "title": "10-year government bond yields and spread",
            "units": "Percent per year", "freq": "Monthly",
            "convention": "Spread = Mexico 10-year Bono M minus U.S. 10-year Treasury. It mixes expected depreciation (inflation) and country risk.",
            "transform": "Both are monthly averages. Bono M is the average rate in Banxico's primary auctions; months with no 10-year auction are blank.",
            "latest": f"{y_now['spread']:.2f} pp", "latest_date": fmt_date(ylds.index[-1], "M"), "srcs": meta("SF30057", "GS10"),
            "traces": [
                {"name": "Mexico 10y (Bono M)", "color": C1, **ser(ylds["mx"], 2)},
                {"name": "U.S. 10y Treasury", "color": C2, **ser(ylds["us"], 2)},
                {"name": "Spread", "color": C3, "dash": "dot", **ser(ylds["spread"], 2)},
            ],
            "yfmt": ".0f", "hover": "%{y:.2f}%",
        },
        {
            "id": "c_vol", "section": "Risk and hedging", "title": "Peso volatility vs. the carry",
            "units": "Percent per year", "freq": "Daily",
            "convention": "Volatility is the one-standard-deviation annual move in USD/MXN; the carry is what an unhedged peso position earns (or a hedge costs) per year. Compare the two to judge whether hedging is worth it.",
            "transform": "Realized volatility = standard deviation of daily log changes in the FIX over the last 21 business days &times; &radic;252 &times; 100. Carry = policy rate differential from the chart above.",
            "latest": f"{vol_now:.1f}% vs {diff_now:.2f}%", "latest_date": fmt_date(vol.index[-1], "D"), "srcs": meta("SF43718", "SF61745", "DFEDTARU", "DFEDTARL"),
            "traces": [
                {"name": "Realized volatility (21-day)", "color": C1, **ser(vol["vol"], 2)},
                {"name": "Carry (rate differential)", "color": C2, "shape": "hv", **ser(vol["carry"], 2)},
            ],
            "yfmt": ".0f", "hover": "%{y:.1f}%",
        },
    ]

    kpis = [
        ("USD/MXN", f"{fx_now:.2f}", f"{fx_1y:+.1f}% over 1 year", fmt_date(fx.index[-1], "D")),
        ("Real exchange rate", f"{rer_now:.0f}", "avg = 100; below = strong peso", fmt_date(rer.index[-1], "M")),
        ("Carry (Banxico &minus; Fed)", f"{diff_now:.2f} pp", "&asymp; annual forward premium", fmt_date(rates.index[-1], "D")),
        ("Inflation gap", f"{inf_mx - inf_us:+.2f} pp", f"Mexico {inf_mx:.2f}%, U.S. {inf_us:.2f}%", fmt_date(infl_last.index[-1], "M")),
        ("Non-oil trade balance", f"US${tb_now['nonoil']:.0f} bn", "last 12 months", fmt_date(trade.index[-1], "M")),
        ("Auto exports", f"{auto_now['yoy12']:+.1f}%", f"US${auto_now['sum12']:.0f} bn, last 12 months", fmt_date(auto.index[-1], "M")),
        ("10y spread vs. U.S.", f"{y_now['spread']:.2f} pp", f"Bono M {y_now['mx']:.2f}%", fmt_date(ylds.index[-1], "M")),
        ("Volatility / carry", f"{vol_now:.1f}% / {diff_now:.1f}%", f"carry-to-risk {ratio:.2f}", fmt_date(vol.index[-1], "D")),
    ]

    status = read_status()
    log = read_log()
    checks = read_verification()
    built = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = render(charts, kpis, reading, status, log, checks, latest, built, finding)
    with open(os.path.join(DOCS, "index.html"), "w") as fh:
        fh.write(page)
    print(f"Built docs/index.html ({len(page)/1024:.0f} KB). Last successful refresh: {status.get('last_successful_refresh_utc', 'n/a')}")


def render(charts, kpis, reading, status, log, checks, latest, built, finding):
    esc = html.escape
    last_ok = status.get("last_successful_refresh_utc", "not yet recorded")
    method = status.get("refresh_method", "")
    attempt_note = ""
    if status.get("last_attempt_utc") and not status.get("last_attempt_ok", True):
        attempt_note = (f"<div class='warn'>&#9888; Last attempt {esc(status['last_attempt_utc'])} could not refresh: "
                        f"{esc(', '.join(status.get('failed_series', [])))}. Charts show the last good data.</div>")

    kpi_html = "".join(
        f"<div class='kpi'><div class='kl'>{k}</div><div class='kv'>{v}</div><div class='ks'>{s}</div><div class='kd'>Latest obs: {dt}</div></div>"
        for k, v, s, dt in kpis)

    sections, cur = [], None
    for c in charts:
        if c["section"] != cur:
            if cur is not None:
                sections.append("</div></section>")
            cur = c["section"]
            sections.append(f"<section><h2>{cur}</h2><div class='grid'>")
        srcs = "; ".join(f"<a href='{s['url']}' target='_blank' rel='noopener'>{esc(s['source'])}</a>" for s in c["srcs"])
        freqs = c["freq"]
        sections.append(f"""
<article class='card'>
  <header><h3>{c['title']}</h3><div class='latest'><span class='lv'>{c['latest']}</span><span class='ld'>Latest observation: {c['latest_date']}</span></div></header>
  <div class='meta'><span><b>Units:</b> {c['units']}</span><span><b>Frequency:</b> {freqs}</span></div>
  <div class='chart' id='{c['id']}'></div>
  <details><summary>Source, convention and transformation</summary>
    <p><b>Source:</b> {srcs}</p>
    <p><b>How to read it:</b> {c['convention']}</p>
    <p><b>Transformation:</b> {c['transform']}</p>
    <p><a href='data/{c['id'][2:]}.csv'>Chart data (CSV)</a></p>
  </details>
</article>""")
    sections.append("</div></section>")

    log_rows = "".join(
        f"<tr><td>{esc(r['time'])}</td><td>{r['ok']} of {r['n']}</td><td>{'&#10003; success' if not r['failed'] else '&#9888; failed: ' + esc(', '.join(r['failed']))}</td></tr>"
        for r in log) or "<tr><td colspan=3>No refresh runs logged yet.</td></tr>"

    lat_rows = "".join(
        f"<tr><td><code>{sid}</code></td><td>{esc(ALL_SERIES[sid]['name'])}</td><td>{esc(ALL_SERIES[sid]['freq'])}</td>"
        f"<td>{dt}</td><td class='num'>{v:,.4f}</td><td><a href='{ALL_SERIES[sid]['url']}' target='_blank' rel='noopener'>{esc(ALL_SERIES[sid]['source'])}</a></td></tr>"
        for sid, (dt, v, n) in latest.items())

    chk_rows = "".join(
        f"<tr><td><code>{esc(c['series'])}</code></td><td>{esc(c['date'])}</td><td class='num'>{esc(c['dashboard_value'])}</td>"
        f"<td class='num'>{esc(c['source_value'])}</td><td>{esc(c['check_source'])}</td><td>{'&#10003; match' if c['match'] == 'yes' else '&#10007; ' + esc(c['match'])}</td></tr>"
        for c in checks) or "<tr><td colspan=6>No manual checks recorded.</td></tr>"

    payload = json.dumps([{k: c[k] for k in ("id", "traces", "yfmt", "hover") if k in c} | {"ref": c.get("ref"), "band": c.get("band"), "ref_label": c.get("ref_label")} for c in charts])
    reading_html = "".join(f"<li>{r}</li>" for r in reading)

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mexico Peso Monitor</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Text:wght@400;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js" charset="utf-8"></script>
<style>
:root{{--surface:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--ink3:#7a7974;--line:#e7e6e2;--accent:#2a78d6}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--surface);color:var(--ink);font:15px/1.5 Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1240px;margin:0 auto;padding:28px 22px 60px}}
h1{{font:400 clamp(28px,3.6vw,40px)/1.1 "Libre Caslon Text",Georgia,serif;margin:2px 0 10px;text-wrap:balance;max-width:900px}}
.eyebrow{{font-weight:700;color:#0b5d63;font-size:14px}} h2{{font:400 22px/1.2 "Libre Caslon Text",Georgia,serif;margin:34px 0 12px;padding-bottom:6px;border-bottom:1px solid var(--line)}} h3{{font-size:16px;margin:0}}
.q{{font-size:17px;color:var(--ink2);margin:0 0 14px}}
.status{{display:flex;flex-wrap:wrap;gap:10px 26px;padding:12px 16px;background:var(--card);border:1px solid var(--line);border-radius:10px;font-size:14px}}
.status b{{color:var(--ink)}} .status span{{color:var(--ink2)}} .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;background:#008300;margin-right:6px}}
.warn{{margin-top:10px;padding:10px 14px;border-radius:8px;background:#fff4e5;border:1px solid #eda100;font-size:14px}}
.kpis{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:16px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.kl{{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink2)}} .kv{{font-size:24px;font-weight:650;margin:2px 0}} .ks{{font-size:13px;color:var(--ink2)}} .kd{{font-size:11.5px;color:var(--ink3);margin-top:4px}}
.reading{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:6px 18px;margin-top:16px}} .reading li{{margin:8px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(520px,1fr));gap:16px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 16px 10px}}
.card header{{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}}
.latest{{text-align:right;white-space:nowrap}} .lv{{display:block;font-weight:650;font-size:16px}} .ld{{display:block;font-size:12px;color:var(--ink2)}}
.meta{{display:flex;flex-wrap:wrap;gap:4px 18px;font-size:13px;color:var(--ink2);margin-top:6px}}
.chart{{height:330px;margin-top:4px}}
details{{font-size:13.5px;color:var(--ink2);border-top:1px solid var(--line);margin-top:6px;padding-top:6px}} summary{{cursor:pointer;color:var(--ink);font-weight:550}} details p{{margin:6px 0}}
a{{color:#1c5cab}} table{{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--card)}} th,td{{text-align:left;padding:7px 9px;border-bottom:1px solid var(--line);vertical-align:top}} th{{color:var(--ink2);font-weight:600}} td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.note{{font-size:13px;color:var(--ink2)}} code{{font-size:12.5px}}
@media (max-width:900px){{.kpis{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
@media (max-width:600px){{.grid{{grid-template-columns:1fr}} .card header{{flex-direction:column}} .latest{{text-align:left}}}}
</style></head>
<body><div class="wrap">
<div class="eyebrow">Mexico Peso Monitor</div>
<h1>{esc(finding)}</h1>
<p class="q"><b>Question:</b> Is the Mexican peso overvalued, and should a U.S. company with peso exposure hedge it?</p>
<div class="status">
  <div><span class="dot"></span><b>Last successful data refresh:</b> <span>{esc(last_ok)}</span></div>
  <div><b>Refresh method:</b> <span>{esc(method) or 'n/a'}</span></div>
  <div><b>Schedule:</b> <span>every weekday at 18:23 UTC (GitHub Actions)</span></div>
  <div><b>Page built:</b> <span>{built}</span></div>
</div>
{attempt_note}
<p class="note" style="margin:8px 2px 0">The refresh time above is when the data were last downloaded. Each chart separately shows the date of its <b>latest observation</b>, which depends on each agency's release calendar.</p>
<div class="kpis">{kpi_html}</div>
<h2>What the data say now</h2>
<ul class="reading">{reading_html}</ul>
<p class="note">These sentences are generated from the latest data on every refresh. They describe the data; they are not a forecast.</p>
{''.join(sections)}
<h2>Data sources and latest observations</h2>
<p class="note">All series come from primary sources: Banco de México (including INEGI data it republishes), the Federal Reserve Board and the U.S. Bureau of Labor Statistics (the last two downloaded through FRED, the St. Louis Fed's database).</p>
<table><thead><tr><th>Series ID</th><th>Series</th><th>Frequency</th><th>Latest observation</th><th class="num">Latest value</th><th>Source</th></tr></thead><tbody>{lat_rows}</tbody></table>
<h2>Verification: dashboard vs. original source</h2>
<p class="note">One observation per series was checked by hand against the publisher's own website or release. Evidence (screenshots) is in the <code>verification/</code> folder of the repository.</p>
<table><thead><tr><th>Series</th><th>Date</th><th class="num">Dashboard</th><th class="num">Source</th><th>Checked against</th><th>Result</th></tr></thead><tbody>{chk_rows}</tbody></table>
<h2>Refresh log (latest runs)</h2>
<table><thead><tr><th>Run time</th><th>Series refreshed</th><th>Result</th></tr></thead><tbody>{log_rows}</tbody></table>
<p class="note" style="margin-top:22px">Built with Python (pandas) and Plotly.js. Code, data and setup instructions are in the repository. Not investment advice.</p>
</div>
<script>
const CHARTS = {payload};
const base = {{
  margin:{{l:46,r:12,t:8,b:34}}, paper_bgcolor:'rgba(0,0,0,0)', plot_bgcolor:'rgba(0,0,0,0)',
  font:{{family:'Inter,-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,sans-serif',size:12,color:'{INK2}'}},
  hovermode:'x unified', hoverlabel:{{bgcolor:'#fff',bordercolor:'{GRID}',font:{{color:'#0b0b0b'}}}},
  legend:{{orientation:'h',x:0,y:1.13,font:{{size:12,color:'#0b0b0b'}}}},
  xaxis:{{type:'date',showgrid:false,linecolor:'{GRID}',ticks:'outside',tickcolor:'{GRID}',showspikes:true,spikemode:'across',spikethickness:1,spikecolor:'#b8b6b0',spikedash:'solid',
    rangeselector:{{x:1,xanchor:'right',y:1.13,bgcolor:'#f1f0ec',activecolor:'#d7e6f8',font:{{size:11}},buttons:[{{count:1,label:'1Y',step:'year',stepmode:'backward'}},{{count:5,label:'5Y',step:'year',stepmode:'backward'}},{{step:'all',label:'All'}}]}}}},
  yaxis:{{gridcolor:'{GRID}',zeroline:false,linecolor:'{GRID}'}}
}};
for (const c of CHARTS) {{
  const single = c.traces.length === 1;
  const data = c.traces.map(t => ({{x:t.x,y:t.y,name:t.name,type:'scatter',mode:'lines',connectgaps:false,
      line:{{color:t.color,width:2,shape:t.shape||'linear',dash:t.dash||'solid'}},hovertemplate:c.hover+'<extra>'+t.name+'</extra>'}}));
  const layout = JSON.parse(JSON.stringify(base));
  layout.yaxis.tickformat = c.yfmt; layout.showlegend = !single;
  if (single) layout.margin.t = 30;
  layout.shapes = []; layout.annotations = [];
  if (c.ref !== null && c.ref !== undefined) {{
    layout.shapes.push({{type:'line',xref:'paper',x0:0,x1:1,y0:c.ref,y1:c.ref,line:{{color:'#8a8984',width:1,dash:'dash'}}}});
    if (c.ref_label) layout.annotations.push({{xref:'paper',x:0.01,y:c.ref,yanchor:'bottom',text:c.ref_label,showarrow:false,font:{{size:11,color:'{INK2}'}}}});
  }}
  if (c.band) {{
    layout.shapes.push({{type:'rect',xref:'paper',x0:0,x1:1,y0:c.band[0],y1:c.band[1],fillcolor:'rgba(120,120,115,0.10)',line:{{width:0}},layer:'below'}});
    layout.annotations.push({{xref:'paper',x:0.01,y:c.band[1],yanchor:'bottom',text:'Banxico target 3% \u00b1 1 pp',showarrow:false,font:{{size:11,color:'{INK2}'}}}});
  }}
  Plotly.newPlot(c.id, data, layout, {{displaylogo:false,responsive:true,modeBarButtonsToRemove:['lasso2d','select2d','autoScale2d']}});
}}
</script>
</body></html>"""


if __name__ == "__main__":
    build()
