# Mexico Peso Monitor

**Question:** Is the Mexican peso overvalued, and should a U.S. company with peso exposure hedge it?

A dashboard of eight indicators drawn from primary sources (Banco de México, INEGI, the Federal Reserve Board, the U.S. Bureau of Labor Statistics). It refreshes itself every weekday through GitHub Actions and is published with GitHub Pages.

| # | Chart | Series | Source | Frequency |
|---|---|---|---|---|
| 1 | USD/MXN exchange rate (FIX), pesos per dollar | SF43718 | Banxico | Daily |
| 2 | Real exchange rate, rebased to January 2003 to present mean = 100 | SR28 | Banxico | Monthly |
| 3 | Banxico target rate, Fed funds target and the differential (carry) | SF61745, DFEDTAR, DFEDTARU, DFEDTARL | Banxico, Federal Reserve | Daily |
| 4 | Headline inflation, Mexico vs. U.S. | SP30578, CPIAUCNS | INEGI via Banxico, BLS | Monthly |
| 5 | Goods trade balance, oil vs. non-oil, 12 month sum | SE28294, SE36600, SE35403 | INEGI/SAT/SE/Banxico | Monthly |
| 6 | Automotive manufacturing exports, 12 month sum | SE28442 | INEGI/SAT/SE/Banxico | Monthly |
| 7 | 10 year Bono M vs. 10 year Treasury and spread | SF30057, GS10 | Banxico, Federal Reserve H.15 | Monthly |
| 8 | Realized USD/MXN volatility vs. the carry | from 1 and 3 | computed | Daily |

U.S. series are downloaded through FRED (St. Louis Fed) but the publishers are the Federal Reserve Board and BLS.

## How it works

```
fetch_data.py        downloads every series in series.py  ->  data/raw/*.csv
                     logs each run                        ->  data/refresh_log.csv, data/status.json
build_dashboard.py   transforms the data                  ->  data/processed/*.csv
                     writes the page                      ->  docs/index.html
.github/workflows/refresh.yml   runs both scripts every weekday at 18:23 UTC and commits the result
```

The page shows the **last successful refresh** (when the data were downloaded) at the top, separately from the **latest observation date** on every chart (which depends on each agency's release calendar). If a download fails, the previous data are kept and the page shows a warning.

## Setup (about 10 minutes, all free)

1. **Get a Banxico API token.** Go to https://www.banxico.org.mx/SieAPIRest/service/v1/token, type the security code and click *Generar token*. Copy the 64 character token.
2. **Create a GitHub repository** (public, so GitHub Pages is free) and upload all files in this folder, keeping the folder structure. The workflow file must end up at `.github/workflows/refresh.yml`. On a Mac the `.github` folder is hidden in Finder (press Cmd+Shift+. to show it), or create the file in GitHub with *Add file > Create new file* and paste its contents.
3. **Add the token as a secret:** repository *Settings > Secrets and variables > Actions > New repository secret*. Name: `BANXICO_TOKEN`. Value: your token.
4. **Allow the workflow to save its results:** *Settings > Actions > General > Workflow permissions >* select *Read and write permissions* > Save.
5. **Turn on the website:** *Settings > Pages > Build and deployment > Deploy from a branch >* branch `main`, folder `/docs` > Save. The dashboard will be at `https://<your-user>.github.io/<repo-name>/`.
6. **Run the first refresh:** *Actions > Refresh dashboard data > Run workflow*. When the run turns green, open it and expand *Download data from Banxico and FRED* to see one line per series (status, number of observations, latest date and value). Take a screenshot of that log as evidence of a successful refresh.

After that it runs by itself every weekday. A run that finds no new releases still counts as a successful refresh: the values just do not change.

## Run it locally (optional)

```bash
pip install -r requirements.txt
export BANXICO_TOKEN=your_token
python fetch_data.py
python build_dashboard.py
open docs/index.html
```

## Verification

`verification/checks.csv` compares one observation of every series with the publisher's own website or release, and `verification/screenshots/` holds the evidence. The same table is shown at the bottom of the dashboard. `data/latest_observations.csv` is regenerated on every build so new checks are easy to repeat.

## Transformations

All of them are in `build_dashboard.py` and described under each chart:

* **Real exchange rate:** Banxico's index (1990 = 100; an increase is a real depreciation of the peso) divided by its January 2003 to latest mean, times 100. January 2003 is when Banxico's permanent 3% inflation target took effect, so the benchmark covers one monetary regime and excludes the 1994 to 1995 crisis overshoot.
* **Sample:** January 2008 onward (Banxico's overnight rate target starts 21 Jan 2008; this keeps the 2008 to 2009 crisis in view), the real exchange rate from January 2003.
* **Fed funds:** the single target rate until 15 Dec 2008, then the midpoint of the target range, (upper + lower) / 2.
* **Real exchange rate estimate:** Banxico's index lags about two months, so months after the latest release are estimated as the latest official value times that month's average FIX over the latest official month's average FIX (current month: month to date). It assumes relative prices and the dollar's value against other partners are unchanged.
* **U.S. inflation:** 12 month % change of the not seasonally adjusted CPI-U, the same basis as Mexico's INPC figure. BLS did not collect October 2025 prices (federal shutdown), so U.S. inflation for October 2025 and October 2026 is left blank, as BLS itself does.
* **Trade and auto exports:** monthly values in thousands of USD, summed over 12 months and shown in billions.
* **10 year spread:** Bono M (monthly average rate in Banxico's primary auctions) minus GS10 (monthly average). Months without a 10 year auction are blank.
* **Realized volatility:** standard deviation of daily log changes in the FIX over 21 business days, times the square root of 252, in %.

## Limitations

* The real exchange rate's long run average is a rough benchmark of "fair value"; productivity growth (Balassa–Samuelson) can move the equilibrium over time.
* The carry approximates the forward premium through covered interest parity; actual forward points also reflect bank spreads and term premia.
* Realized volatility looks backward; options markets price expected volatility, which is not available from a free primary source.
* Trade data are revised by INEGI and Banxico; the first ("oportuna") figures can change.
* Banxico's real exchange rate for late 2025 uses a Cleveland Fed nowcast for the missing U.S. CPI, as Banxico notes on its table.
