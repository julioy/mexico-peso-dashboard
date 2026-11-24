"""Series catalogue for the Mexico peso dashboard.

Every raw series the dashboard uses is listed here once, with its primary
source, identifier, native units and frequency. fetch_data.py downloads
exactly these series; build_dashboard.py turns them into the eight charts.
"""

# Sample start for most charts: January 2008. Banxico has targeted the overnight
# interbank rate since 21 Jan 2008 (series SF61745 starts then), and starting
# here keeps the 2008-09 global financial crisis, the largest peso sell-off
# before COVID, in view for the hedging question. It also covers the 2016 U.S.
# election shock, COVID, the 2022-23 hiking cycle and the 2023 "super peso".
SAMPLE_START = "2008-01-01"

# Benchmark for the real exchange rate: January 2003, when Banxico's permanent
# 3% (+/- 1 pp) inflation target took effect. Earlier years mix the 1994-95
# Tequila crisis overshoot and high inflation with the current regime, so a
# 1995-present mean would not be a like-for-like "normal" level.
RER_START = "2003-01-01"

BANXICO = {
    "SF43718": {
        "name": "USD/MXN exchange rate, FIX",
        "units": "Mexican pesos per U.S. dollar",
        "freq": "Daily (business days)",
        "source": "Banco de México, SIE (series SF43718)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=6&accion=consultarCuadro&idCuadro=CF102&locale=es",
    },
    "SR28": {
        "name": "Real exchange rate index (111 countries, CPI based)",
        "units": "Index, 1990 = 100 as published",
        "freq": "Monthly",
        "source": "Banco de México, SIE (series SR28)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=6&accion=consultarCuadro&idCuadro=CR60&locale=es",
    },
    "SF61745": {
        "name": "Banxico target interest rate",
        "units": "Percent per year",
        "freq": "Daily",
        "source": "Banco de México, SIE (series SF61745)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=18&accion=consultarCuadro&idCuadro=CF101&locale=es",
    },
    "SP30578": {
        "name": "Mexico headline inflation (INPC), annual",
        "units": "Percent, year over year",
        "freq": "Monthly",
        "source": "INEGI, published by Banco de México SIE (series SP30578)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=8&accion=consultarCuadro&idCuadro=CP151&locale=es",
    },
    "SE28294": {
        "name": "Goods trade balance, total",
        "units": "Thousands of U.S. dollars per month",
        "freq": "Monthly",
        "source": "INEGI/SAT/SE/Banxico, Banco de México SIE (series SE28294)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=1&accion=consultarCuadro&idCuadro=CE125&locale=es",
    },
    "SE36600": {
        "name": "Goods trade balance, oil",
        "units": "Thousands of U.S. dollars per month",
        "freq": "Monthly",
        "source": "INEGI/SAT/SE/Banxico, Banco de México SIE (series SE36600)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=1&accion=consultarCuadro&idCuadro=CE125&locale=es",
    },
    "SE35403": {
        "name": "Goods trade balance, non-oil",
        "units": "Thousands of U.S. dollars per month",
        "freq": "Monthly",
        "source": "INEGI/SAT/SE/Banxico, Banco de México SIE (series SE35403)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=1&accion=consultarCuadro&idCuadro=CE125&locale=es",
    },
    "SE28442": {
        "name": "Automotive manufacturing exports",
        "units": "Thousands of U.S. dollars per month",
        "freq": "Monthly",
        "source": "INEGI/SAT/SE/Banxico, Banco de México SIE (series SE28442)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=1&accion=consultarCuadro&idCuadro=CE171&locale=es",
    },
    "SF30057": {
        "name": "10-year fixed-rate government bond (Bono M) yield",
        "units": "Percent per year, monthly average of primary auctions",
        "freq": "Monthly",
        "source": "Banco de México, SIE (series SF30057)",
        "url": "https://www.banxico.org.mx/SieInternet/consultarDirectorioInternetAction.do?sector=18&accion=consultarCuadro&idCuadro=CF114&locale=es",
    },
}

# U.S. series. FRED is only the delivery channel: the original publishers are
# the Federal Reserve Board and the Bureau of Labor Statistics.
FRED = {
    "DFEDTAR": {
        "name": "Fed funds target rate (single target, until 15 Dec 2008)",
        "units": "Percent per year",
        "freq": "Daily",
        "source": "Federal Reserve Board, via FRED (DFEDTAR)",
        "url": "https://fred.stlouisfed.org/series/DFEDTAR",
    },
    "DFEDTARU": {
        "name": "Fed funds target range, upper limit",
        "units": "Percent per year",
        "freq": "Daily",
        "source": "Federal Reserve Board, via FRED (DFEDTARU)",
        "url": "https://fred.stlouisfed.org/series/DFEDTARU",
    },
    "DFEDTARL": {
        "name": "Fed funds target range, lower limit",
        "units": "Percent per year",
        "freq": "Daily",
        "source": "Federal Reserve Board, via FRED (DFEDTARL)",
        "url": "https://fred.stlouisfed.org/series/DFEDTARL",
    },
    "CPIAUCNS": {
        "name": "U.S. CPI, all urban consumers, not seasonally adjusted",
        "units": "Index, 1982-84 = 100",
        "freq": "Monthly",
        "source": "U.S. Bureau of Labor Statistics, via FRED (CPIAUCNS)",
        "url": "https://fred.stlouisfed.org/series/CPIAUCNS",
    },
    "GS10": {
        "name": "10-year U.S. Treasury yield, constant maturity",
        "units": "Percent per year, monthly average",
        "freq": "Monthly",
        "source": "Federal Reserve Board H.15, via FRED (GS10)",
        "url": "https://fred.stlouisfed.org/series/GS10",
    },
}

ALL_SERIES = {**{k: {**v, "provider": "banxico"} for k, v in BANXICO.items()},
              **{k: {**v, "provider": "fred"} for k, v in FRED.items()}}

# Banxico uses this number as a "no data" placeholder in some series.
BANXICO_MISSING = -989898.0
