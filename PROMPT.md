# Prompt used to build the dashboard

The dashboard was built with Claude (Anthropic's AI agent, running with a code workspace and browser access). The work came out of a short conversation. The two prompts that defined the build are below, followed by the specification the agent worked from.

## 1. Choosing the indicators

> Suggest the dashboards needed for Mexico, 4 to 8, like the ones you put [USD/MXN spot, real effective exchange rate, Banxico vs. Fed policy rate, Mexico vs. U.S. inflation, remittances or the trade balance, 10 year M bono or a sovereign spread] but what else? Or maybe some trade information, or commodities that Mexico exports that affect the peso. Keep the 8 most important.

The agent's answer, which I adopted: USD/MXN spot, real exchange rate, Banxico–Fed rate differential, inflation differential, goods trade balance split into oil and non-oil, automotive exports, 10 year Bono M–Treasury spread, and realized volatility. Oil prices, remittances, FDI and CFTC positioning were dropped (oil is now under about 5% of Mexico's exports and Mexico is a net fuel importer, so oil is a weak driver of the peso).

## 2. Building it

> Choose one country whose economy you would like to monitor. Use an AI coding agent to build a dashboard that helps answer your question and updates automatically as new data become available.
>
> 1. Select and present your data. Choose 4–8 relevant indicators. Use reliable primary sources, such as central banks, national statistical agencies, or international organizations. For each chart, report the units, data frequency, source, and latest observation date. Specify exchange rate quotation conventions and explain any transformations, such as growth rates or rebasing an index. Choose a sample period that provides enough context to interpret recent developments.
> 2. Automate and verify the refresh. Configure the dashboard to retrieve data and update its charts on a regular schedule. Display the date and time of the last successful refresh separately from the latest observation date. Check at least one observation from each series against its original source. Demonstrate a successful refresh using a screenshot or log.
> 3. Submit your dashboard, your prompt, and evidence of verification.
>
> I have never worked with Claude Code, so can you do this on your own? I want it to be very well made, informative, easy to follow, and to follow the instructions above.

## 3. Specification the agent worked to

* **Country and question:** Mexico. Is the peso overvalued, and should a U.S. company with peso exposure hedge it?
* **Data:** primary sources only. Banco de México's SIE API (token based) for USD/MXN FIX, the real exchange rate, the target rate, INPC inflation, trade balances, automotive exports and the 10 year Bono M yield. Federal Reserve Board and BLS series (through FRED's CSV download) for the Fed target range, the U.S. CPI and the 10 year Treasury yield. Find the official series IDs in Banxico's API catalogue rather than guessing them.
* **Charts:** eight charts in four sections (exchange rate; carry and inflation; trade; risk and hedging). Each card shows title, units, frequency, source with a link, latest value and latest observation date, the quotation convention, and the transformation applied. Sample from 2015; the real exchange rate from January 2003, when Banxico's permanent 3% inflation target took effect, so its average is a like-for-like benchmark. Hover tooltips, 1Y/5Y/All range buttons, CSV download per chart, and the same colour for the same entity across charts.
* **Header:** last successful refresh time (from the automated run) shown separately from observation dates; key figures; a short, auto-generated "what the data say now" that only states facts.
* **Automation:** GitHub Actions on a weekday schedule runs `fetch_data.py` then `build_dashboard.py`, commits the data and page, and GitHub Pages serves `docs/`. Keep the last good data if a source fails, and log every run per series.
* **Verification:** compare one observation per series with the publisher's own website or release and keep screenshots; show the results table on the dashboard.
* **Code quality:** plain Python (pandas), every transformation in one file with comments, README with step-by-step setup for someone new to GitHub.

## How AI was used, and what was checked by hand

The agent found the official series IDs in Banxico's API catalogue, pulled the initial data through the browser, wrote the code, rendered the page to check the layout, and checked one observation per series against Banxico, INEGI, the Federal Reserve, BLS and the U.S. Treasury. Verification also caught a real issue: BLS never collected U.S. prices for October 2025, so a naive 12 month change would have compared the wrong months. The code now leaves those months blank, the same way BLS does.
