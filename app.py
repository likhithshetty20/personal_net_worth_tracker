from flask import Flask, request, jsonify, render_template_string
import os
import json
import uuid
from datetime import datetime
import requests

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(BASE_DIR, "data.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")

DEFAULT_DATA = {
    "assets": {
        "crypto": [],
        "indian_stocks": [],
        "us_stocks": [],
        "mutual_funds": [],
        "bank_accounts": [],
        "gold": [],
        "property": [],
        "other": []
    },
    "liabilities": {
        "loans": [],
        "other": []
    },
    "history": []
}

DEFAULT_SETTINGS = {
    "refresh_minutes": 5,
    "coingecko_api_key": "",
    "twelve_data_api_key": ""
}


# ============================================================
# JSON STORAGE
# ============================================================

def save_json(path, data):
    temp = path + ".tmp"

    with open(temp, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False
        )

    os.replace(temp, path)


def load_json(path, default):
    if not os.path.exists(path):
        save_json(path, default)
        return json.loads(json.dumps(default))

    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return json.loads(json.dumps(default))


def load_data():
    data = load_json(DATA_FILE, DEFAULT_DATA)

    for category in DEFAULT_DATA["assets"]:
        data["assets"].setdefault(category, [])

    for category in DEFAULT_DATA["liabilities"]:
        data["liabilities"].setdefault(category, [])

    data.setdefault("history", [])

    return data


def load_settings():
    return load_json(
        SETTINGS_FILE,
        DEFAULT_SETTINGS
    )


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ============================================================
# HTTP API HELPER
# ============================================================

def api_get(url, params=None, headers=None):

    response = requests.get(
        url,
        params=params or {},
        headers=headers or {},
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# USD / INR
# ============================================================

def get_usd_inr():

    try:

        result = api_get(
            "https://api.frankfurter.dev/v2/rate/USD/INR"
        )

        return number(
            result.get("rate")
        )

    except Exception:

        return 0


# ============================================================
# CRYPTO
# ============================================================

def get_crypto_prices(items, settings):

    coin_ids = []

    for item in items:

        coin_id = str(
            item.get(
                "coingecko_id",
                ""
            )
        ).strip()

        if coin_id:
            coin_ids.append(coin_id)

    coin_ids = list(
        dict.fromkeys(
            coin_ids
        )
    )

    if not coin_ids:
        return {}

    headers = {
        "accept": "application/json"
    }

    api_key = str(
        settings.get(
            "coingecko_api_key",
            ""
        )
    ).strip()

    if api_key:

        headers[
            "x-cg-demo-api-key"
        ] = api_key

    try:

        return api_get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={
                "ids": ",".join(coin_ids),
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_last_updated_at": "true"
            },
            headers=headers
        )

    except Exception:

        return {}


# ============================================================
# YAHOO FINANCE
# ============================================================

def get_yahoo_price(symbol):

    try:

        url = (
            "https://query1.finance.yahoo.com/"
            "v8/finance/chart/"
            + requests.utils.quote(
                symbol,
                safe=""
            )
        )

        result = api_get(
            url,
            params={
                "range": "1d",
                "interval": "1m"
            }
        )

        metadata = (
            result[
                "chart"
            ][
                "result"
            ][0][
                "meta"
            ]
        )

        return {
            "price": number(
                metadata.get(
                    "regularMarketPrice"
                )
            ),
            "currency": metadata.get(
                "currency",
                "USD"
            ),
            "source": "Yahoo Finance"
        }

    except Exception:

        return None


# ============================================================
# TWELVE DATA
# ============================================================

def get_twelve_data_price(
    symbol,
    api_key
):

    if not api_key:
        return None

    try:

        result = api_get(
            "https://api.twelvedata.com/price",
            params={
                "symbol": symbol,
                "apikey": api_key
            }
        )

        if result.get("price") is not None:

            return {
                "price": number(
                    result["price"]
                ),
                "currency": "USD",
                "source": "Twelve Data"
            }

    except Exception:

        pass

    return None


# ============================================================
# MUTUAL FUND NAV
# ============================================================

def get_mutual_fund_nav(
    scheme_code
):

    if not str(
        scheme_code
    ).strip():

        return None

    try:

        result = api_get(
            "https://api.mfapi.in/mf/"
            + str(scheme_code)
            + "/latest"
        )

        rows = result.get(
            "data",
            []
        )

        if rows:

            row = rows[0]

            return {
                "price": number(
                    row.get("nav")
                ),
                "date": row.get(
                    "date"
                ),
                "source": "MFapi.in"
            }

    except Exception:

        pass

    return None


# ============================================================
# MARKET DATA
# ============================================================

def get_market_data():

    data = load_data()
    settings = load_settings()

    market = {

        "prices": {

            "crypto": {},
            "indian_stocks": {},
            "us_stocks": {},
            "mutual_funds": {}

        },

        "usd_inr": get_usd_inr(),

        "timestamp":
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            )

    }

    # --------------------------------------------------------
    # CRYPTO
    # --------------------------------------------------------

    crypto_prices = get_crypto_prices(
        data["assets"]["crypto"],
        settings
    )

    for item in data[
        "assets"
    ][
        "crypto"
    ]:

        coin_id = str(
            item.get(
                "coingecko_id",
                ""
            )
        ).strip()

        if coin_id in crypto_prices:

            market[
                "prices"
            ][
                "crypto"
            ][
                item["id"]
            ] = crypto_prices[
                coin_id
            ]

    # --------------------------------------------------------
    # INDIAN STOCKS
    # --------------------------------------------------------

    for item in data[
        "assets"
    ][
        "indian_stocks"
    ]:

        symbol = str(
            item.get(
                "symbol",
                ""
            )
        ).strip()

        if not symbol:
            continue

        api_key = str(
            settings.get(
                "twelve_data_api_key",
                ""
            )
        ).strip()

        price = get_twelve_data_price(
            symbol,
            api_key
        )

        if not price:

            exchange = str(
                item.get(
                    "exchange",
                    "NSE"
                )
            ).upper()

            yahoo_symbol = symbol

            if "." not in yahoo_symbol:

                if exchange == "BSE":

                    yahoo_symbol += ".BO"

                else:

                    yahoo_symbol += ".NS"

            price = get_yahoo_price(
                yahoo_symbol
            )

        if price:

            market[
                "prices"
            ][
                "indian_stocks"
            ][
                item["id"]
            ] = price

    # --------------------------------------------------------
    # US STOCKS
    # --------------------------------------------------------

    for item in data[
        "assets"
    ][
        "us_stocks"
    ]:

        symbol = str(
            item.get(
                "symbol",
                ""
            )
        ).strip()

        if not symbol:
            continue

        api_key = str(
            settings.get(
                "twelve_data_api_key",
                ""
            )
        ).strip()

        price = get_twelve_data_price(
            symbol,
            api_key
        )

        if not price:

            price = get_yahoo_price(
                symbol
            )

        if price:

            market[
                "prices"
            ][
                "us_stocks"
            ][
                item["id"]
            ] = price

    # --------------------------------------------------------
    # MUTUAL FUNDS
    # --------------------------------------------------------

    for item in data[
        "assets"
    ][
        "mutual_funds"
    ]:

        nav = get_mutual_fund_nav(
            item.get(
                "scheme_code"
            )
        )

        if nav:

            market[
                "prices"
            ][
                "mutual_funds"
            ][
                item["id"]
            ] = nav

    return market


# ============================================================
# CURRENT ASSET VALUE
# ============================================================

def get_asset_value(
    category,
    item,
    market
):

    price = (
        market
        .get("prices", {})
        .get(category, {})
        .get(item["id"])
    )

    # CRYPTO

    if category == "crypto" and price:

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                price.get("usd")
            )
            *
            number(
                market.get("usd_inr")
            )
        )

    # INDIAN STOCK

    if (
        category == "indian_stocks"
        and price
    ):

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                price.get("price")
            )
        )

    # US STOCK

    if (
        category == "us_stocks"
        and price
    ):

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                price.get("price")
            )
            *
            number(
                market.get("usd_inr")
            )
        )

    # MUTUAL FUND

    if (
        category == "mutual_funds"
        and price
    ):

        return (
            number(
                item.get("units")
            )
            *
            number(
                price.get("price")
            )
        )

    # MANUAL ASSET

    return number(
        item.get(
            "current_value",
            0
        )
    )


# ============================================================
# INVESTED VALUE
# ============================================================

def get_invested_value(
    category,
    item,
    market
):

    usd_inr = number(
        market.get("usd_inr")
    )

    if category == "crypto":

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                item.get(
                    "buy_price_usd"
                )
            )
            *
            usd_inr
        )

    if category == "indian_stocks":

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                item.get(
                    "buy_price_inr"
                )
            )
        )

    if category == "us_stocks":

        return (
            number(
                item.get("quantity")
            )
            *
            number(
                item.get(
                    "buy_price_usd"
                )
            )
            *
            usd_inr
        )

    if category == "mutual_funds":

        return (
            number(
                item.get("units")
            )
            *
            number(
                item.get(
                    "buy_price_nav"
                )
            )
        )

    return 0


# ============================================================
# CALCULATE TOTALS
# ============================================================

def calculate_totals(
    data,
    market
):

    totals = {

        "crypto": 0,
        "indian_stocks": 0,
        "us_stocks": 0,
        "mutual_funds": 0,
        "bank_accounts": 0,
        "gold": 0,
        "property": 0,
        "other": 0,

        "loans": 0,
        "other_liabilities": 0

    }

    asset_categories = [

        "crypto",
        "indian_stocks",
        "us_stocks",
        "mutual_funds",
        "bank_accounts",
        "gold",
        "property",
        "other"

    ]

    for category in asset_categories:

        for item in data[
            "assets"
        ][
            category
        ]:

            totals[
                category
            ] += get_asset_value(
                category,
                item,
                market
            )

    for loan in data[
        "liabilities"
    ][
        "loans"
    ]:

        totals[
            "loans"
        ] += number(
            loan.get(
                "outstanding"
            )
        )

    for liability in data[
        "liabilities"
    ][
        "other"
    ]:

        totals[
            "other_liabilities"
        ] += number(
            liability.get(
                "current_value"
            )
        )

    return totals


# ============================================================
# HTML APPLICATION
# ============================================================

HTML = r"""
<!DOCTYPE html>

<html lang="en">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>My Net Worth</title>

<script
    src="https://cdn.jsdelivr.net/npm/chart.js">
</script>

<style>

* {
    box-sizing: border-box;
}

body {

    margin: 0;

    background: #f4f6fa;

    color: #182033;

    font-family:
        Inter,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

}

header {

    background: white;

    border-bottom:
        1px solid #e2e6ee;

    padding:
        18px 5%;

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 20px;

    position: sticky;

    top: 0;

    z-index: 20;

}

.logo h1 {

    margin: 0;

    font-size: 24px;

}

.logo p {

    margin:
        4px 0 0;

    color: #727c90;

    font-size: 13px;

}

.header-actions {

    display: flex;

    gap: 8px;

    flex-wrap: wrap;

}

button {

    border: 0;

    border-radius: 9px;

    padding:
        10px 14px;

    background: #315bea;

    color: white;

    font-weight: 600;

    cursor: pointer;

}

button:hover {

    opacity: .9;

}

button.secondary {

    background: #e9edf5;

    color: #26314a;

}

button.danger {

    background: #ffe6e6;

    color: #c62828;

}

main {

    width: min(
        1250px,
        92%
    );

    margin: auto;

    padding:
        28px 0 60px;

}


/* HERO */

.hero {

    background:
        linear-gradient(
            135deg,
            #172554,
            #315bea
        );

    color: white;

    border-radius: 22px;

    padding: 30px;

    display: flex;

    justify-content: space-between;

    gap: 30px;

}

.hero-label {

    font-size: 11px;

    letter-spacing: 1.5px;

    opacity: .75;

}

.net-worth {

    font-size: 44px;

    font-weight: 800;

    margin-top: 6px;

}

.hero-note {

    margin-top: 7px;

    font-size: 12px;

    opacity: .75;

}

.hero-stats {

    display: grid;

    grid-template-columns:
        repeat(2, 180px);

    gap: 10px;

}

.hero-stat {

    background:
        rgba(
            255,
            255,
            255,
            .11
        );

    border-radius: 12px;

    padding: 15px;

}

.hero-stat span {

    display: block;

    font-size: 12px;

    opacity: .7;

}

.hero-stat strong {

    display: block;

    margin-top: 5px;

    font-size: 18px;

}


/* SUMMARY */

.summary {

    margin-top: 18px;

    display: grid;

    grid-template-columns:
        repeat(4, 1fr);

    gap: 12px;

}

.card {

    background: white;

    border:
        1px solid #e2e6ee;

    border-radius: 14px;

    padding: 17px;

}

.card-icon {

    font-size: 23px;

}

.card span {

    display: block;

    color: #737d91;

    font-size: 12px;

    margin-top: 7px;

}

.card strong {

    display: block;

    margin-top: 5px;

    font-size: 19px;

}


/* PANEL */

.panel {

    margin-top: 18px;

    background: white;

    border:
        1px solid #e2e6ee;

    border-radius: 17px;

    padding: 20px;

}

.panel-header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    gap: 15px;

    margin-bottom: 16px;

}

.panel-header h2 {

    margin: 0;

    font-size: 18px;

}

.panel-header p {

    margin:
        4px 0 0;

    color: #737d91;

    font-size: 12px;

}


/* TABLE */

.table-wrapper {

    overflow-x: auto;

}

table {

    width: 100%;

    border-collapse: collapse;

}

th,
td {

    padding:
        12px 8px;

    border-bottom:
        1px solid #edf0f4;

    text-align: left;

    white-space: nowrap;

}

th {

    color: #737d91;

    font-size: 12px;

    font-weight: 600;

}

td {

    font-size: 13px;

}

.small {

    color: #737d91;

    font-size: 11px;

    margin-top: 3px;

}

.positive {

    color: #159566;

}

.negative {

    color: #d9363e;

}

.actions {

    white-space: nowrap;

}

.actions button {

    padding:
        6px 9px;

    font-size: 11px;

    margin-left: 4px;

}


/* CHART */

.chart {

    height: 300px;

}


/* MODAL */

.modal {

    position: fixed;

    inset: 0;

    background:
        rgba(
            0,
            0,
            0,
            .55
        );

    display: flex;

    align-items: center;

    justify-content: center;

    padding: 18px;

    z-index: 100;

}

.hidden {

    display: none;

}

.modal-box {

    width:
        min(
            650px,
            100%
        );

    max-height: 90vh;

    overflow-y: auto;

    background: white;

    border-radius: 18px;

    padding: 22px;

}

.modal-header {

    display: flex;

    justify-content: space-between;

    align-items: center;

    margin-bottom: 18px;

}

.modal-header h2 {

    margin: 0;

}

.close {

    background: #edf0f5;

    color: #222;

    font-size: 20px;

    padding:
        5px 10px;

}


/* ASSET SELECTOR */

.asset-types {

    display: grid;

    grid-template-columns:
        repeat(2, 1fr);

    gap: 10px;

}

.asset-type {

    background: #f8f9fc;

    color: #182033;

    border:
        1px solid #dfe4ed;

    text-align: left;

    padding: 16px;

    border-radius: 12px;

}

.asset-type:hover {

    border-color: #315bea;

    background: #f1f4ff;

}

.asset-type .icon {

    font-size: 25px;

}

.asset-type strong {

    display: block;

    margin-top: 7px;

}

.asset-type span {

    display: block;

    margin-top: 3px;

    color: #737d91;

    font-size: 11px;

}


/* FORM */

label {

    display: block;

    margin:
        12px 0;

    color: #59647a;

    font-size: 13px;

}

input,
select {

    width: 100%;

    margin-top: 6px;

    padding: 11px;

    border-radius: 9px;

    border:
        1px solid #dfe4ed;

    background: white;

    color: #182033;

}

.form-actions {

    display: flex;

    justify-content: flex-end;

    gap: 8px;

    margin-top: 20px;

}


/* RESPONSIVE */

@media(max-width:900px) {

    .hero {

        flex-direction: column;

    }

    .summary {

        grid-template-columns:
            repeat(2, 1fr);

    }

}

@media(max-width:600px) {

    header {

        flex-direction: column;

        align-items: flex-start;

    }

    .summary {

        grid-template-columns: 1fr;

    }

    .hero-stats {

        grid-template-columns:
            repeat(2, 1fr);

    }

    .asset-types {

        grid-template-columns: 1fr;

    }

    .net-worth {

        font-size: 35px;

    }

}

</style>

</head>


<body>


<header>

    <div class="logo">

        <h1>My Net Worth</h1>

        <p>
            Personal Wealth Dashboard • INR ₹
        </p>

    </div>


    <div class="header-actions">

        <button onclick="refreshAll()">

            ↻ Refresh Prices

        </button>


        <button
            class="secondary"
            onclick="saveSnapshot()">

            Save Snapshot

        </button>


        <button
            class="secondary"
            onclick="openSettings()">

            ⚙ Settings

        </button>

    </div>

</header>


<main>


<!-- ========================================================
     NET WORTH
     ======================================================== -->

<section class="hero">

    <div>

        <div class="hero-label">

            TOTAL NET WORTH

        </div>


        <div
            id="netWorth"
            class="net-worth">

            ₹0

        </div>


        <div
            id="lastRefresh"
            class="hero-note">

            Loading market data...

        </div>

    </div>


    <div class="hero-stats">

        <div class="hero-stat">

            <span>
                Total Assets
            </span>

            <strong id="totalAssets">
                ₹0
            </strong>

        </div>


        <div class="hero-stat">

            <span>
                Total Liabilities
            </span>

            <strong id="totalLiabilities">
                ₹0
            </strong>

        </div>


        <div class="hero-stat">

            <span>
                USD / INR
            </span>

            <strong id="usdInr">
                —
            </strong>

        </div>


        <div class="hero-stat">

            <span>
                Currency
            </span>

            <strong>
                INR ₹
            </strong>

        </div>

    </div>

</section>


<!-- ========================================================
     SUMMARY CARDS
     ======================================================== -->

<section class="summary">


    <div class="card">

        <div class="card-icon">
            🪙
        </div>

        <span>
            Crypto
        </span>

        <strong id="cryptoValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🇮🇳
        </div>

        <span>
            Indian Stocks
        </span>

        <strong id="indianStocksValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🇺🇸
        </div>

        <span>
            US Stocks
        </span>

        <strong id="usStocksValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            📈
        </div>

        <span>
            Mutual Funds
        </span>

        <strong id="mutualFundsValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🏦
        </div>

        <span>
            Bank Accounts
        </span>

        <strong id="bankValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🥇
        </div>

        <span>
            Gold
        </span>

        <strong id="goldValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🏠
        </div>

        <span>
            Land / Property
        </span>

        <strong id="propertyValue">
            ₹0
        </strong>

    </div>


    <div class="card">

        <div class="card-icon">
            🏦
        </div>

        <span>
            Loans
        </span>

        <strong id="loanValue">
            ₹0
        </strong>

    </div>


</section>


<!-- ========================================================
     ASSET ALLOCATION
     ======================================================== -->

<section class="panel">

    <div class="panel-header">

        <div>

            <h2>
                Asset Allocation
            </h2>

            <p>
                Your complete wealth distribution
            </p>

        </div>

    </div>


    <div class="chart">

        <canvas
            id="allocationChart">
        </canvas>

    </div>

</section>


<!-- ========================================================
     ASSETS
     ======================================================== -->

<section class="panel">

    <div class="panel-header">

        <div>

            <h2>
                Assets
            </h2>

            <p>
                Investments and manually entered assets
            </p>

        </div>


        <button
            onclick="openAssetSelector()">

            + Add Asset

        </button>

    </div>


    <div
        id="assetTable"
        class="table-wrapper">

    </div>

</section>


<!-- ========================================================
     LOANS
     ======================================================== -->

<section class="panel">

    <div class="panel-header">

        <div>

            <h2>
                Loans & Liabilities
            </h2>

            <p>
                Outstanding debt is deducted from net worth
            </p>

        </div>


        <button
            onclick="openForm('loans')">

            + Add Loan

        </button>

    </div>


    <div
        id="loanTable"
        class="table-wrapper">

    </div>

</section>


<!-- ========================================================
     HISTORY
     ======================================================== -->

<section class="panel">

    <div class="panel-header">

        <div>

            <h2>
                Net Worth History
            </h2>

            <p>
                Saved snapshots of your net worth
            </p>

        </div>

    </div>


    <div class="chart">

        <canvas
            id="historyChart">
        </canvas>

    </div>

</section>


</main>


<!-- ========================================================
     ASSET TYPE SELECTOR
     ======================================================== -->

<div
    id="assetSelector"
    class="modal hidden">

    <div class="modal-box">

        <div class="modal-header">

            <h2>
                Add Asset
            </h2>


            <button
                class="close"
                onclick="closeAssetSelector()">

                ×

            </button>

        </div>


        <p class="form-title">

            What do you want to add?

        </p>


        <div class="asset-types">


            <button
                class="asset-type"
                onclick="chooseAsset('crypto')">

                <div class="icon">
                    🪙
                </div>

                <strong>
                    Cryptocurrency
                </strong>

                <span>
                    Bitcoin, Ethereum, Solana, etc.
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('indian_stocks')">

                <div class="icon">
                    🇮🇳
                </div>

                <strong>
                    Indian Stock
                </strong>

                <span>
                    NSE / BSE shares
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('us_stocks')">

                <div class="icon">
                    🇺🇸
                </div>

                <strong>
                    US Stock
                </strong>

                <span>
                    NASDAQ / NYSE shares
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('mutual_funds')">

                <div class="icon">
                    📈
                </div>

                <strong>
                    Mutual Fund
                </strong>

                <span>
                    Indian mutual funds
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('bank_accounts')">

                <div class="icon">
                    🏦
                </div>

                <strong>
                    Bank Account
                </strong>

                <span>
                    Savings, current, FD, etc.
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('gold')">

                <div class="icon">
                    🥇
                </div>

                <strong>
                    Gold
                </strong>

                <span>
                    Jewellery, coins, bars, etc.
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('property')">

                <div class="icon">
                    🏠
                </div>

                <strong>
                    Land / Property
                </strong>

                <span>
                    House, land, apartment, etc.
                </span>

            </button>


            <button
                class="asset-type"
                onclick="chooseAsset('other')">

                <div class="icon">
                    💰
                </div>

                <strong>
                    Other Asset
                </strong>

                <span>
                    Anything else you own
                </span>

            </button>


        </div>

    </div>

</div>


<!-- ========================================================
     ITEM FORM
     ======================================================== -->

<div
    id="formModal"
    class="modal hidden">

    <div class="modal-box">

        <div class="modal-header">

            <h2 id="formTitle">
                Add Asset
            </h2>


            <button
                class="close"
                onclick="closeForm()">

                ×

            </button>

        </div>


        <form
            id="itemForm"
            onsubmit="submitItem(event)">

            <div id="formFields"></div>


            <input
                type="hidden"
                id="formCategory">


            <input
                type="hidden"
                id="formId">


            <div class="form-actions">

                <button
                    type="button"
                    class="secondary"
                    onclick="closeForm()">

                    Cancel

                </button>


                <button type="submit">

                    Save

                </button>

            </div>

        </form>

    </div>

</div>


<!-- ========================================================
     SETTINGS
     ======================================================== -->

<div
    id="settingsModal"
    class="modal hidden">

    <div class="modal-box">

        <div class="modal-header">

            <h2>
                Settings
            </h2>


            <button
                class="close"
                onclick="closeSettings()">

                ×

            </button>

        </div>


        <form
            onsubmit="submitSettings(event)">


            <label>

                Market refresh interval

                <input
                    id="refreshMinutes"
                    type="number"
                    min="1"
                    max="1440">

            </label>


            <label>

                CoinGecko Demo API Key
                <span class="small">
                    Optional
                </span>

                <input
                    id="coingeckoKey"
                    type="password"
                    placeholder="Optional">

            </label>


            <label>

                Twelve Data API Key
                <span class="small">
                    Optional
                </span>

                <input
                    id="twelveDataKey"
                    type="password"
                    placeholder="Optional">

            </label>


            <div class="form-actions">

                <button
                    type="button"
                    class="secondary"
                    onclick="closeSettings()">

                    Cancel

                </button>


                <button>

                    Save Settings

                </button>

            </div>


        </form>

    </div>

</div>


<script>


// ==========================================================
// GLOBAL VARIABLES
// ==========================================================

let DATA = null;

let MARKET = null;

let SETTINGS = null;

let allocationChart = null;

let historyChart = null;

let refreshTimer = null;


// ==========================================================
// FIELD DEFINITIONS
// ==========================================================

const FIELDS = {


    crypto: [

        [
            "name",
            "Coin name",
            "text",
            true
        ],

        [
            "coingecko_id",
            "CoinGecko ID (example: solana)",
            "text",
            true
        ],

        [
            "quantity",
            "Quantity owned",
            "number",
            true
        ],

        [
            "buy_price_usd",
            "Average purchase price (USD)",
            "number",
            false
        ]

    ],


    indian_stocks: [

        [
            "name",
            "Company name",
            "text",
            true
        ],

        [
            "symbol",
            "NSE / BSE symbol",
            "text",
            true
        ],

        [
            "exchange",
            "Exchange",
            "select",
            true
        ],

        [
            "quantity",
            "Number of shares",
            "number",
            true
        ],

        [
            "buy_price_inr",
            "Average purchase price (₹)",
            "number",
            false
        ]

    ],


    us_stocks: [

        [
            "name",
            "Company name",
            "text",
            true
        ],

        [
            "symbol",
            "US ticker",
            "text",
            true
        ],

        [
            "quantity",
            "Number of shares",
            "number",
            true
        ],

        [
            "buy_price_usd",
            "Average purchase price (USD)",
            "number",
            false
        ]

    ],


    mutual_funds: [

        [
            "name",
            "Mutual fund name",
            "text",
            true
        ],

        [
            "scheme_code",
            "MFapi scheme code",
            "text",
            true
        ],

        [
            "units",
            "Units",
            "number",
            true
        ],

        [
            "buy_price_nav",
            "Average purchase NAV (₹)",
            "number",
            false
        ]

    ],


    bank_accounts: [

        [
            "name",
            "Bank / account name",
            "text",
            true
        ],

        [
            "current_value",
            "Current balance (₹)",
            "number",
            true
        ]

    ],


    gold: [

        [
            "name",
            "Gold holding",
            "text",
            true
        ],

        [
            "quantity_grams",
            "Weight (grams)",
            "number",
            false
        ],

        [
            "current_value",
            "Current estimated value (₹)",
            "number",
            true
        ]

    ],


    property: [

        [
            "name",
            "Property / land name",
            "text",
            true
        ],

        [
            "purchase_value",
            "Purchase value (₹)",
            "number",
            false
        ],

        [
            "current_value",
            "Current estimated value (₹)",
            "number",
            true
        ]

    ],


    other: [

        [
            "name",
            "Asset name",
            "text",
            true
        ],

        [
            "current_value",
            "Current value (₹)",
            "number",
            true
        ]

    ],


    loans: [

        [
            "name",
            "Loan name",
            "text",
            true
        ],

        [
            "original_amount",
            "Original loan amount (₹)",
            "number",
            false
        ],

        [
            "outstanding",
            "Current outstanding balance (₹)",
            "number",
            true
        ],

        [
            "interest_rate",
            "Interest rate (%)",
            "number",
            false
        ],

        [
            "emi",
            "Monthly EMI (₹)",
            "number",
            false
        ]

    ],


    other_liabilities: [

        [
            "name",
            "Liability name",
            "text",
            true
        ],

        [
            "current_value",
            "Current amount (₹)",
            "number",
            true
        ]

    ]

};


// ==========================================================
// HELPERS
// ==========================================================

function money(value) {

    return new Intl.NumberFormat(
        "en-IN",
        {
            style: "currency",
            currency: "INR",
            maximumFractionDigits: 0
        }
    ).format(
        Number(value) || 0
    );

}


function num(value) {

    const result =
        Number(value);

    return Number.isFinite(
        result
    )
        ? result
        : 0;

}


function escapeHtml(value) {

    return String(
        value ?? ""
    ).replace(
        /[&<>"']/g,
        function(character) {

            const map = {

                "&": "&amp;",

                "<": "&lt;",

                ">": "&gt;",

                '"': "&quot;",

                "'": "&#039;"

            };

            return map[
                character
            ];

        }
    );

}


async function api(
    url,
    options = {}
) {

    const response =
        await fetch(
            url,
            options
        );


    const result =
        await response.json();


    if (!response.ok) {

        throw new Error(
            result.error
            ||
            "Request failed"
        );

    }


    return result;

}


// ==========================================================
// LOAD DATA
// ==========================================================

async function loadData() {

    DATA =
        await api(
            "/api/data"
        );


    SETTINGS =
        await api(
            "/api/settings"
        );

}


// ==========================================================
// REFRESH MARKET
// ==========================================================

async function refreshMarket() {

    try {

        MARKET =
            await api(
                "/api/market"
            );


        render();

    }

    catch (error) {

        console.error(
            error
        );

        render();

    }

}


// ==========================================================
// VALUE
// ==========================================================

function assetValue(
    category,
    item
) {

    const price =
        MARKET
            ?.prices
            ?.[category]
            ?.[item.id];


    if (
        category === "crypto"
        &&
        price
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                price.usd
            )

            *

            num(
                MARKET.usd_inr
            )

        );

    }


    if (
        category === "indian_stocks"
        &&
        price
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                price.price
            )

        );

    }


    if (
        category === "us_stocks"
        &&
        price
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                price.price
            )

            *

            num(
                MARKET.usd_inr
            )

        );

    }


    if (
        category === "mutual_funds"
        &&
        price
    ) {

        return (

            num(
                item.units
            )

            *

            num(
                price.price
            )

        );

    }


    return num(
        item.current_value
    );

}


// ==========================================================
// INVESTMENT VALUE
// ==========================================================

function investedValue(
    category,
    item
) {

    const usdInr =
        num(
            MARKET?.usd_inr
        );


    if (
        category === "crypto"
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                item.buy_price_usd
            )

            *

            usdInr

        );

    }


    if (
        category === "indian_stocks"
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                item.buy_price_inr
            )

        );

    }


    if (
        category === "us_stocks"
    ) {

        return (

            num(
                item.quantity
            )

            *

            num(
                item.buy_price_usd
            )

            *

            usdInr

        );

    }


    if (
        category === "mutual_funds"
    ) {

        return (

            num(
                item.units
            )

            *

            num(
                item.buy_price_nav
            )

        );

    }


    return 0;

}


// ==========================================================
// TOTALS
// ==========================================================

function calculateTotals() {

    const totals = {

        crypto: 0,

        indian_stocks: 0,

        us_stocks: 0,

        mutual_funds: 0,

        bank_accounts: 0,

        gold: 0,

        property: 0,

        other: 0,

        loans: 0,

        other_liabilities: 0

    };


    const assetCategories = [

        "crypto",

        "indian_stocks",

        "us_stocks",

        "mutual_funds",

        "bank_accounts",

        "gold",

        "property",

        "other"

    ];


    for (
        const category
        of assetCategories
    ) {

        for (
            const item
            of DATA.assets[category]
        ) {

            totals[category] +=
                assetValue(
                    category,
                    item
                );

        }

    }


    for (
        const loan
        of DATA.liabilities.loans
    ) {

        totals.loans +=
            num(
                loan.outstanding
            );

    }


    for (
        const liability
        of DATA.liabilities.other
    ) {

        totals.other_liabilities +=
            num(
                liability.current_value
            );

    }


    return totals;

}


// ==========================================================
// RENDER
// ==========================================================

function render() {

    if (
        !DATA
        ||
        !MARKET
    ) {

        return;

    }


    const totals =
        calculateTotals();


    const assetCategories = [

        "crypto",

        "indian_stocks",

        "us_stocks",

        "mutual_funds",

        "bank_accounts",

        "gold",

        "property",

        "other"

    ];


    let totalAssets = 0;


    for (
        const category
        of assetCategories
    ) {

        totalAssets +=
            totals[category];

    }


    const totalLiabilities =
        totals.loans
        +
        totals.other_liabilities;


    const netWorth =
        totalAssets
        -
        totalLiabilities;


    document
        .getElementById(
            "netWorth"
        )
        .textContent =
        money(
            netWorth
        );


    document
        .getElementById(
            "totalAssets"
        )
        .textContent =
        money(
            totalAssets
        );


    document
        .getElementById(
            "totalLiabilities"
        )
        .textContent =
        money(
            totalLiabilities
        );


    document
        .getElementById(
            "usdInr"
        )
        .textContent =
        MARKET.usd_inr
        ?
        "₹"
        +
        MARKET.usd_inr.toFixed(2)
        :
        "—";


    document
        .getElementById(
            "lastRefresh"
        )
        .textContent =
        "Last market refresh: "
        +
        new Date(
            MARKET.timestamp
        ).toLocaleTimeString();


    const summary = {

        cryptoValue:
            totals.crypto,

        indianStocksValue:
            totals.indian_stocks,

        usStocksValue:
            totals.us_stocks,

        mutualFundsValue:
            totals.mutual_funds,

        bankValue:
            totals.bank_accounts,

        goldValue:
            totals.gold,

        propertyValue:
            totals.property,

        loanValue:
            totals.loans

    };


    for (
        const id
        in summary
    ) {

        document
            .getElementById(id)
            .textContent =
            money(
                summary[id]
            );

    }


    renderAssets();

    renderLoans();

    renderCharts(
        totals
    );

}


// ==========================================================
// ASSET TABLE
// ==========================================================

function renderAssets() {

    const categoryNames = {

        crypto:
            "Cryptocurrency",

        indian_stocks:
            "Indian Stock",

        us_stocks:
            "US Stock",

        mutual_funds:
            "Mutual Fund",

        bank_accounts:
            "Bank Account",

        gold:
            "Gold",

        property:
            "Land / Property",

        other:
            "Other Asset"

    };


    const rows = [];


    for (
        const category
        of Object.keys(
            categoryNames
        )
    ) {

        for (
            const item
            of DATA.assets[category]
        ) {

            const value =
                assetValue(
                    category,
                    item
                );


            const invested =
                investedValue(
                    category,
                    item
                );


            const pnl =
                value
                -
                invested;


            const marketPrice =
                MARKET
                    ?.prices
                    ?.[category]
                    ?.[item.id];


            let priceText =
                "Manual";


            if (
                category === "crypto"
                &&
                marketPrice
            ) {

                priceText =
                    "$"
                    +
                    num(
                        marketPrice.usd
                    ).toLocaleString(
                        undefined,
                        {
                            maximumFractionDigits: 8
                        }
                    );

            }


            else if (
                (
                    category ===
                    "indian_stocks"
                    ||
                    category ===
                    "us_stocks"
                )
                &&
                marketPrice
            ) {

                priceText =
                    num(
                        marketPrice.price
                    ).toLocaleString(
                        undefined,
                        {
                            maximumFractionDigits: 4
                        }
                    );

            }


            else if (
                category ===
                "mutual_funds"
                &&
                marketPrice
            ) {

                priceText =
                    "₹"
                    +
                    num(
                        marketPrice.price
                    ).toFixed(4);

            }


            rows.push(`

                <tr>

                    <td>

                        <b>
                            ${escapeHtml(
                                item.name
                            )}
                        </b>

                        <div class="small">

                            ${categoryNames[
                                category
                            ]}

                        </div>

                    </td>


                    <td>
                        ${priceText}
                    </td>


                    <td>
                        ${money(value)}
                    </td>


                    <td class="${
                        pnl >= 0
                        ? "positive"
                        : "negative"
                    }">

                        ${
                            invested
                            ?
                            (
                                pnl >= 0
                                ? "+"
                                : ""
                            )
                            +
                            money(pnl)
                            :
                            "—"
                        }

                    </td>


                    <td class="actions">

                        <button
                            onclick='editItem(
                                "${category}",
                                "${item.id}"
                            )'>

                            Edit

                        </button>


                        <button
                            class="danger"
                            onclick='deleteItem(
                                "${category}",
                                "${item.id}"
                            )'>

                            Delete

                        </button>

                    </td>

                </tr>

            `);

        }

    }


    if (!rows.length) {

        document
            .getElementById(
                "assetTable"
            )
            .innerHTML = `

                <div
                    class="small"
                    style="
                        padding:25px;
                        text-align:center;
                    ">

                    No assets added yet.

                    Click
                    <b>
                        + Add Asset
                    </b>
                    to begin.

                </div>

            `;

        return;

    }


    document
        .getElementById(
            "assetTable"
        )
        .innerHTML = `

        <table>

            <thead>

                <tr>

                    <th>
                        Asset
                    </th>

                    <th>
                        Market Price
                    </th>

                    <th>
                        Current Value
                    </th>

                    <th>
                        P&L
                    </th>

                    <th></th>

                </tr>

            </thead>


            <tbody>

                ${rows.join("")}

            </tbody>

        </table>

    `;

}


// ==========================================================
// LOAN TABLE
// ==========================================================

function renderLoans() {

    const loans = [

        ...DATA.liabilities.loans.map(
            item => ({
                ...item,
                category:
                    "loans"
            })
        ),

        ...DATA.liabilities.other.map(
            item => ({
                ...item,
                category:
                    "other_liabilities"
            })
        )

    ];


    if (!loans.length) {

        document
            .getElementById(
                "loanTable"
            )
            .innerHTML = `

                <div
                    class="small"
                    style="
                        padding:25px;
                        text-align:center;
                    ">

                    No loans or liabilities
                    added yet.

                </div>

            `;

        return;

    }


    document
        .getElementById(
            "loanTable"
        )
        .innerHTML = `

        <table>

            <thead>

                <tr>

                    <th>
                        Loan
                    </th>

                    <th>
                        Outstanding
                    </th>

                    <th>
                        Interest
                    </th>

                    <th>
                        EMI
                    </th>

                    <th></th>

                </tr>

            </thead>


            <tbody>

                ${loans.map(
                    loan => `

                    <tr>

                        <td>

                            <b>
                                ${escapeHtml(
                                    loan.name
                                )}
                            </b>

                        </td>


                        <td>

                            ${money(
                                loan.outstanding
                                ??
                                loan.current_value
                            )}

                        </td>


                        <td>

                            ${
                                loan.interest_rate
                                ?
                                loan.interest_rate
                                + "%"
                                :
                                "—"
                            }

                        </td>


                        <td>

                            ${
                                loan.emi
                                ?
                                money(
                                    loan.emi
                                )
                                :
                                "—"
                            }

                        </td>


                        <td class="actions">

                            <button
                                onclick='editItem(
                                    "${loan.category}",
                                    "${loan.id}"
                                )'>

                                Edit

                            </button>


                            <button
                                class="danger"
                                onclick='deleteItem(
                                    "${loan.category}",
                                    "${loan.id}"
                                )'>

                                Delete

                            </button>

                        </td>

                    </tr>

                `
                ).join("")}

            </tbody>

        </table>

    `;

}


// ==========================================================
// CHARTS
// ==========================================================

function renderCharts(
    totals
) {

    const labels = [

        "Crypto",

        "Indian Stocks",

        "US Stocks",

        "Mutual Funds",

        "Bank",

        "Gold",

        "Property",

        "Other"

    ];


    const values = [

        totals.crypto,

        totals.indian_stocks,

        totals.us_stocks,

        totals.mutual_funds,

        totals.bank_accounts,

        totals.gold,

        totals.property,

        totals.other

    ];


    if (
        allocationChart
    ) {

        allocationChart.destroy();

    }


    allocationChart =
        new Chart(

            document.getElementById(
                "allocationChart"
            ),

            {

                type:
                    "doughnut",

                data: {

                    labels,

                    datasets: [

                        {
                            data:
                                values
                        }

                    ]

                },

                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    plugins: {

                        legend: {

                            position:
                                "bottom"

                        },

                        tooltip: {

                            callbacks: {

                                label:
                                    function(
                                        context
                                    ) {

                                        return (

                                            context.label
                                            +
                                            ": "
                                            +
                                            money(
                                                context.raw
                                            )

                                        );

                                    }

                            }

                        }

                    }

                }

            }

        );


    if (
        historyChart
    ) {

        historyChart.destroy();

    }


    const history =
        DATA.history || [];


    historyChart =
        new Chart(

            document.getElementById(
                "historyChart"
            ),

            {

                type:
                    "line",

                data: {

                    labels:
                        history.map(
                            item =>
                                new Date(
                                    item.date
                                ).toLocaleDateString()
                        ),

                    datasets: [

                        {

                            label:
                                "Net Worth (₹)",

                            data:
                                history.map(
                                    item =>
                                        item.net_worth
                                ),

                            tension:
                                0.25

                        }

                    ]

                },

                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    scales: {

                        y: {

                            ticks: {

                                callback:
                                    value =>
                                        money(
                                            value
                                        )

                            }

                        }

                    }

                }

            }

        );

}


// ==========================================================
// ASSET SELECTOR
// ==========================================================

function openAssetSelector() {

    document
        .getElementById(
            "assetSelector"
        )
        .classList.remove(
            "hidden"
        );

}


function closeAssetSelector() {

    document
        .getElementById(
            "assetSelector"
        )
        .classList.add(
            "hidden"
        );

}


function chooseAsset(
    category
) {

    closeAssetSelector();

    openForm(
        category
    );

}


// ==========================================================
// FORM
// ==========================================================

function openForm(
    category,
    existing = null
) {

    const isEdit =
        existing !== null;


    if (!existing) {

        existing = {};

    }


    document
        .getElementById(
            "formCategory"
        )
        .value =
        category;


    document
        .getElementById(
            "formId"
        )
        .value =
        existing.id || "";


    const names = {

        crypto:
            "Cryptocurrency",

        indian_stocks:
            "Indian Stock",

        us_stocks:
            "US Stock",

        mutual_funds:
            "Mutual Fund",

        bank_accounts:
            "Bank Account",

        gold:
            "Gold",

        property:
            "Land / Property",

        other:
            "Other Asset",

        loans:
            "Loan",

        other_liabilities:
            "Other Liability"

    };


    document
        .getElementById(
            "formTitle"
        )
        .textContent =

        (
            isEdit
            ?
            "Edit "
            :
            "Add "
        )
        +
        (
            names[category]
            ||
            "Item"
        );


    const fields =
        FIELDS[category] || [];


    document
        .getElementById(
            "formFields"
        )
        .innerHTML =

        fields.map(
            field => {

                const [
                    key,
                    label,
                    type,
                    required
                ] = field;


                if (
                    type ===
                    "select"
                ) {

                    const exchange =
                        existing[
                            key
                        ]
                        ||
                        "NSE";


                    return `

                        <label>

                            ${label}

                            <select
                                name="${key}"
                                ${
                                    required
                                    ?
                                    "required"
                                    :
                                    ""
                                }>

                                <option
                                    value="NSE"
                                    ${
                                        exchange ===
                                        "NSE"
                                        ?
                                        "selected"
                                        :
                                        ""
                                    }>

                                    NSE

                                </option>


                                <option
                                    value="BSE"
                                    ${
                                        exchange ===
                                        "BSE"
                                        ?
                                        "selected"
                                        :
                                        ""
                                    }>

                                    BSE

                                </option>

                            </select>

                        </label>

                    `;

                }


                return `

                    <label>

                        ${label}

                        <input

                            name="${key}"

                            type="${type}"

                            step="any"

                            value="${escapeHtml(
                                existing[
                                    key
                                ]
                                ??
                                ""
                            )}"

                            ${
                                required
                                ?
                                "required"
                                :
                                ""
                            }

                        >

                    </label>

                `;

            }
        ).join("");



    document
        .getElementById(
            "formModal"
        )
        .classList.remove(
            "hidden"
        );

}


function editItem(
    category,
    id
) {

    let collection =
        DATA.assets[
            category
        ];


    if (!collection) {

        collection =
            DATA.liabilities[
                category
            ];

    }


    if (!collection) {

        return;

    }


    const item =
        collection.find(
            entry =>
                entry.id === id
        );


    if (item) {

        openForm(
            category,
            item
        );

    }

}


function closeForm() {

    document
        .getElementById(
            "formModal"
        )
        .classList.add(
            "hidden"
        );

}


// ==========================================================
// SAVE ITEM
// ==========================================================

async function submitItem(event) {

    event.preventDefault();

    try {

        const category =
            document.getElementById(
                "formCategory"
            ).value;

        const id =
            document.getElementById(
                "formId"
            ).value;

        const form =
            document.getElementById(
                "itemForm"
            );

        const formData =
            new FormData(form);

        const values = {};

        formData.forEach(
            (value, key) => {

                values[key] = value;

            }
        );

        values.category = category;

        /*
         * Convert numeric fields to numbers.
         */
        const numericFields = [
            "quantity",
            "buy_price_usd",
            "buy_price_inr",
            "units",
            "buy_price_nav",
            "current_value",
            "quantity_grams",
            "purchase_value",
            "original_amount",
            "outstanding",
            "interest_rate",
            "emi"
        ];

        numericFields.forEach(
            key => {

                if (
                    values[key] !== undefined &&
                    values[key] !== ""
                ) {

                    values[key] =
                        Number(values[key]);

                }

            }
        );

        /*
         * Create or update the item.
         */
        let response;

        if (id) {

            response = await fetch(
                "/api/item/" + id,
                {
                    method: "PUT",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(values)
                }
            );

        } else {

            response = await fetch(
                "/api/item",
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(values)
                }
            );

        }

        const result =
            await response.json();

        if (!response.ok) {

            throw new Error(
                result.error ||
                "Unable to save item"
            );

        }

        /*
         * Close the form.
         */
        closeForm();

        /*
         * Reload data and prices.
         */
        await loadData();

        await refreshMarket();

    } catch (error) {

        console.error(
            "Save error:",
            error
        );

        alert(
            "Could not save the item:\n\n" +
            error.message
        );

    }

}

// ==========================================================
// DELETE
// ==========================================================

async function deleteItem(
    category,
    id
) {

    if (
        !confirm(
            "Delete this item?"
        )
    ) {

        return;

    }


    await api(

        "/api/item/"
        +
        category
        +
        "/"
        +
        id,

        {
            method:
                "DELETE"
        }

    );


    await loadData();

    await refreshMarket();

}


// ==========================================================
// SNAPSHOT
// ==========================================================

async function saveSnapshot() {

    const totals =
        calculateTotals();


    const categories = [

        "crypto",

        "indian_stocks",

        "us_stocks",

        "mutual_funds",

        "bank_accounts",

        "gold",

        "property",

        "other"

    ];


    let assets = 0;


    for (
        const category
        of categories
    ) {

        assets +=
            totals[
                category
            ];

    }


    const liabilities =
        totals.loans
        +
        totals.other_liabilities;


    await api(
        "/api/snapshot",
        {

            method:
                "POST",

            headers: {

                "Content-Type":
                    "application/json"

            },

            body:
                JSON.stringify({

                    net_worth:
                        assets
                        -
                        liabilities,

                    assets,

                    liabilities

                })

        }
    );


    await loadData();

    render();


    alert(
        "Net worth snapshot saved."
    );

}


// ==========================================================
// SETTINGS
// ==========================================================

function openSettings() {

    document
        .getElementById(
            "refreshMinutes"
        )
        .value =
        SETTINGS.refresh_minutes;


    document
        .getElementById(
            "coingeckoKey"
        )
        .value = "";


    document
        .getElementById(
            "twelveDataKey"
        )
        .value = "";


    document
        .getElementById(
            "settingsModal"
        )
        .classList.remove(
            "hidden"
        );

}


function closeSettings() {

    document
        .getElementById(
            "settingsModal"
        )
        .classList.add(
            "hidden"
        );

}


async function submitSettings(
    event
) {

    event.preventDefault();


    await api(
        "/api/settings",
        {

            method:
                "POST",

            headers: {

                "Content-Type":
                    "application/json"

            },

            body:
                JSON.stringify({

                    refresh_minutes:
                        num(
                            document
                                .getElementById(
                                    "refreshMinutes"
                                )
                                .value
                        ),

                    coingecko_api_key:
                        document
                            .getElementById(
                                "coingeckoKey"
                            )
                            .value,

                    twelve_data_api_key:
                        document
                            .getElementById(
                                "twelveDataKey"
                            )
                            .value

                })

        }
    );


    closeSettings();


    SETTINGS =
        await api(
            "/api/settings"
        );


    scheduleRefresh();


    alert(
        "Settings saved."
    );

}


// ==========================================================
// REFRESH
// ==========================================================

function scheduleRefresh() {

    if (refreshTimer) {

        clearInterval(
            refreshTimer
        );

    }


    const minutes =
        SETTINGS?.refresh_minutes
        ||
        5;


    refreshTimer =
        setInterval(
            refreshMarket,
            minutes * 60 * 1000
        );

}


async function refreshAll() {

    await loadData();

    await refreshMarket();

}


// ==========================================================
// START
// ==========================================================

(async function start() {

    try {

        await loadData();

        await refreshMarket();

        scheduleRefresh();

    }

    catch (error) {

        console.error(
            error
        );

        alert(
            "Unable to load the application. Check the Ubuntu terminal."
        );

    }

})();

</script>

</body>

</html>
"""


# ============================================================
# FLASK ROUTES
# ============================================================

@app.route("/")
def home():

    return render_template_string(
        HTML
    )


@app.route("/api/data")
def api_data():

    return jsonify(
        load_data()
    )


@app.route("/api/settings")
def api_settings():

    settings = load_settings()

    return jsonify({

        "refresh_minutes":
            settings.get(
                "refresh_minutes",
                5
            ),

        "has_coingecko_key":
            bool(
                settings.get(
                    "coingecko_api_key"
                )
            ),

        "has_twelve_data_key":
            bool(
                settings.get(
                    "twelve_data_api_key"
                )
            )

    })


@app.route(
    "/api/settings",
    methods=["POST"]
)
def update_settings():

    settings = load_settings()

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    settings[
        "refresh_minutes"
    ] = max(

        1,

        min(

            1440,

            int(
                number(
                    body.get(
                        "refresh_minutes",
                        5
                    )
                )
            )

        )

    )


    if (
        body.get(
            "coingecko_api_key"
        )
        is not None
        and
        body.get(
            "coingecko_api_key"
        ) != ""
    ):

        settings[
            "coingecko_api_key"
        ] = str(
            body[
                "coingecko_api_key"
            ]
        ).strip()


    if (
        body.get(
            "twelve_data_api_key"
        )
        is not None
        and
        body.get(
            "twelve_data_api_key"
        ) != ""
    ):

        settings[
            "twelve_data_api_key"
        ] = str(
            body[
                "twelve_data_api_key"
            ]
        ).strip()


    save_json(
        SETTINGS_FILE,
        settings
    )


    return jsonify({
        "ok": True
    })


@app.route("/api/market")
def api_market():

    return jsonify(
        get_market_data()
    )


# ============================================================
# CREATE ITEM
# ============================================================

@app.route(
    "/api/item",
    methods=["POST"]
)
def create_item():

    body = request.get_json(
            silent=True
        ) or {}


    category = body.pop(
            "category",
            None
        )


    if (
        category
        in
        DEFAULT_DATA[
            "assets"
        ]
    ):

        section = "assets"

    elif (
        category
        in
        DEFAULT_DATA[
            "liabilities"
        ]
    ):

        section = "liabilities"

    else:

        return jsonify({

            "error":
                "Invalid category"

        }), 400


    body["id"] = str(
            uuid.uuid4()
        )


    data = load_data()


    data[
        section
    ][
        category
    ].append(
        body
    )


    save_json(
        DATA_FILE,
        data
    )


    return jsonify({

        "ok": True,

        "item": body

    })


# ============================================================
# UPDATE ITEM
# ============================================================

@app.route(
    "/api/item/<item_id>",
    methods=["PUT"]
)
def update_item(item_id):

    body = request.get_json(
            silent=True
        ) or {}


    category = body.pop(
            "category",
            None
        )


    if (
        category
        in
        DEFAULT_DATA[
            "assets"
        ]
    ):

        section = "assets"

    elif (
        category
        in
        DEFAULT_DATA[
            "liabilities"
        ]
    ):

        section = "liabilities"

    else:

        return jsonify({

            "error":
                "Invalid category"

        }), 400


    data = load_data()


    for item in data[
        section
    ][
        category
    ]:

        if (
            item.get("id")
            ==
            item_id
        ):

            item.clear()

            item.update(
                body
            )

            item["id"] = item_id


            save_json(
                DATA_FILE,
                data
            )


            return jsonify({
                "ok": True
            })


    return jsonify({

        "error":
            "Item not found"

    }), 404


# ============================================================
# DELETE ITEM
# ============================================================

@app.route(
    "/api/item/<category>/<item_id>",
    methods=["DELETE"]
)
def delete_item(
    category,
    item_id
):

    if (
        category
        in
        DEFAULT_DATA[
            "assets"
        ]
    ):

        section = "assets"

    elif (
        category
        in
        DEFAULT_DATA[
            "liabilities"
        ]
    ):

        section = "liabilities"

    else:

        return jsonify({

            "error":
                "Invalid category"

        }), 400


    data = load_data()


    original_length =len(
            data[
                section
            ][
                category
            ]
        )


    data[
        section
    ][
        category
    ] = [

        item

        for item

        in data[
            section
        ][
            category
        ]

        if item.get(
            "id"
        )
        !=
        item_id

    ]


    if (
        len(
            data[
                section
            ][
                category
            ]
        )
        ==
        original_length
    ):

        return jsonify({

            "error":
                "Item not found"

        }), 404


    save_json(
        DATA_FILE,
        data
    )


    return jsonify({
        "ok": True
    })


# ============================================================
# SNAPSHOT
# ============================================================

@app.route(
    "/api/snapshot",
    methods=["POST"]
)
def create_snapshot():

    body = request.get_json(
            silent=True
        ) or {}


    data = load_data()


    data[
        "history"
    ].append({

        "date":
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            ),

        "net_worth":
            number(
                body.get(
                    "net_worth"
                )
            ),

        "assets":
            number(
                body.get(
                    "assets"
                )
            ),

        "liabilities":
            number(
                body.get(
                    "liabilities"
                )
            )

    })


    data[
        "history"
    ] = data[
        "history"
    ][-3650:]


    save_json(
        DATA_FILE,
        data
    )


    return jsonify({
        "ok": True
    })


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    app.run(

        host="127.0.0.1",

        port=5000,

        debug=False

    )